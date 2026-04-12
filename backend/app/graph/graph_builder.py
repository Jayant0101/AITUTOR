import re

import networkx as nx
try:
    import spacy
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    spacy = None


class KnowledgeGraph:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        if spacy is None:
            self.nlp = None
        else:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                self.nlp = None

    def build_from_chunks(self, chunks: list[dict]) -> None:
        self.graph.clear()
        parent_stack: list[tuple[int, str]] = []

        for chunk in chunks:
            level = int(chunk["level"])
            content = str(chunk.get("content", ""))
            heading = str(chunk.get("heading", ""))
            entities = self._extract_entities(f"{heading}\n{content}")

            enriched_chunk = dict(chunk)
            enriched_chunk["entities"] = entities
            enriched_chunk["keywords"] = self._extract_keywords(heading, content)
            self.graph.add_node(enriched_chunk["id"], **enriched_chunk)

            if level <= 0:
                parent_stack = [(level, enriched_chunk["id"])]
                continue

            while parent_stack and parent_stack[-1][0] >= level:
                parent_stack.pop()

            if parent_stack:
                parent_id = parent_stack[-1][1]
                self.graph.add_edge(parent_id, enriched_chunk["id"], kind="hierarchy")

            parent_stack.append((level, enriched_chunk["id"]))

    def _extract_entities(self, text: str) -> list[str]:
        if not self.nlp or not text.strip():
            return []

        doc = self.nlp(text)
        candidates: list[str] = []

        for chunk in doc.noun_chunks:
            value = chunk.text.strip().lower()
            if value:
                candidates.append(value)

        for entity in doc.ents:
            value = entity.text.strip().lower()
            if value:
                candidates.append(value)

        unique: list[str] = []
        seen = set()
        for item in candidates:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    def _extract_keywords(self, heading: str, content: str) -> list[str]:
        heading_terms = re.findall(r"[a-zA-Z0-9]{3,}", heading.lower())
        content_terms = re.findall(r"[a-zA-Z0-9]{4,}", content.lower())
        keywords = heading_terms + content_terms[:25]

        unique: list[str] = []
        seen = set()
        for token in keywords:
            if token not in seen:
                seen.add(token)
                unique.append(token)
        return unique
