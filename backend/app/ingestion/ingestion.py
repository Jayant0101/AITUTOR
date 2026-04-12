import hashlib
import re
from pathlib import Path


class MarkdownParser:
    def __init__(self) -> None:
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def parse_file(self, filepath: str, source_name: str | None = None) -> list[dict]:
        file_path = Path(filepath)
        with file_path.open("r", encoding="utf-8") as handle:
            content = handle.read()

        source = source_name or file_path.name
        return self.parse_text(content=content, source=source)

    def parse_directory(self, directory: str) -> list[dict]:
        base = Path(directory)
        if not base.exists():
            return []

        all_chunks: list[dict] = []
        for path in sorted(base.rglob("*.md")):
            relative_source = str(path.relative_to(base)).replace("\\", "/")
            chunks = self.parse_file(str(path), source_name=relative_source)
            all_chunks.extend(chunks)
        return all_chunks

    def parse_text(self, content: str, source: str = "inline") -> list[dict]:
        chunks: list[dict] = []
        parts = re.split(r"^(#{1,6})\s+(.+)$", content, flags=re.MULTILINE)

        if parts and parts[0].strip():
            chunks.append(
                {
                    "id": self._generate_id(
                        source=source, heading="Root", level=0, index=0
                    ),
                    "level": 0,
                    "heading": "Root",
                    "content": parts[0].strip(),
                    "source": source,
                }
            )

        chunk_index = len(chunks)
        for i in range(1, len(parts), 3):
            level_str = parts[i]
            heading_text = parts[i + 1].strip()
            body_text = parts[i + 2].strip() if i + 2 < len(parts) else ""
            level = len(level_str)

            chunks.append(
                {
                    "id": self._generate_id(
                        source=source,
                        heading=heading_text,
                        level=level,
                        index=chunk_index,
                    ),
                    "level": level,
                    "heading": heading_text,
                    "content": body_text,
                    "source": source,
                }
            )
            chunk_index += 1

        return chunks

    def _generate_id(self, source: str, heading: str, level: int, index: int) -> str:
        base = f"{source}|{level}|{index}|{heading}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]

