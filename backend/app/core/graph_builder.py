import networkx as nx
import spacy

class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        # Ensure spacy model is downloaded (python -m spacy download en_core_web_sm)
        # Try loading, if it fails, fallback to bare loading later or inform user
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback or initialization indicator
            self.nlp = None

    def build_from_chunks(self, chunks: list[dict]):
        parent_stack = []

        for chunk in chunks:
            level = chunk['level']
            # Enrich chunk with entities
            entities = self._extract_entities(chunk['content'])
            chunk['entities'] = entities

            # Add node
            self.graph.add_node(chunk['id'], **chunk)

            # Determine hierarchy
            if level == 0:
                parent_stack = [(level, chunk['id'])]
                continue
                
            # Maintain the parent stack
            while parent_stack and parent_stack[-1][0] >= level:
                parent_stack.pop()
            
            if parent_stack:
                parent_id = parent_stack[-1][1]
                self.graph.add_edge(parent_id, chunk['id'])

            parent_stack.append((level, chunk['id']))

    def _extract_entities(self, text: str) -> list[str]:
        if not self.nlp or not text:
            return []
            
        doc = self.nlp(text)
        # Extract noun chunks for keyword associations
        return [chunk.text for chunk in doc.noun_chunks]
