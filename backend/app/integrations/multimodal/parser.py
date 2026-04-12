from __future__ import annotations

from typing import Any

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None


class MultimodalParser:
    def __init__(self) -> None:
        pass

    def parse_pdf(self, path: str) -> dict[str, Any]:
        text = ""
        if PdfReader is not None:
            try:
                reader = PdfReader(path)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                text = ""
        return {"text": text, "path": path, "type": "pdf"}

    def parse_image(self, path: str) -> dict[str, Any]:
        return {"text": "", "path": path, "type": "image"}
