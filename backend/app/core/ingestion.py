import re
import hashlib

class MarkdownParser:
    def __init__(self):
        # Match headings like # Heading 1 or ### Heading 3
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    def parse_file(self, filepath: str) -> list[dict]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return self.parse_text(content)

    def parse_text(self, content: str) -> list[dict]:
        chunks = []
        # Split the text based on headings.
        # This regex will keep the # level and the heading text as groups, followed by the content until the next heading.
        parts = re.split(r'^(#{1,6})\s+(.+)$', content, flags=re.MULTILINE)
        
        # If there's content before the first heading, parts[0] has it
        if parts[0].strip():
            chunks.append({
                'id': self._generate_id("root", ""),
                'level': 0,
                'heading': "Root",
                'content': parts[0].strip()
            })

        # Process the rest
        for i in range(1, len(parts), 3):
            level_str = parts[i]
            heading_text = parts[i+1].strip()
            body_text = parts[i+2].strip() if i+2 < len(parts) else ""
            
            level = len(level_str)
            chunk_id = self._generate_id(heading_text, str(level))
            
            chunks.append({
                'id': chunk_id,
                'level': level,
                'heading': heading_text,
                'content': body_text
            })

        return chunks

    def _generate_id(self, heading: str, level_str: str) -> str:
        base = f"{level_str}_{heading}"
        return hashlib.md5(base.encode('utf-8')).hexdigest()[:8]

