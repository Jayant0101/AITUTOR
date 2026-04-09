from rank_bm25 import BM25Okapi
import networkx as nx

class RetrievalEngine:
    def __init__(self, knowledge_graph):
        """
        Expects an instance of `KnowledgeGraph` from graph_builder.py
        """
        self.kg = knowledge_graph
        self.bm25 = None
        self.node_ids = []
        
        # Build the index upon initialization if the graph has nodes
        self._build_index()

    def _build_index(self):
        corpus = []
        self.node_ids = []
        
        for node_id, data in self.kg.graph.nodes(data=True):
            self.node_ids.append(node_id)
            
            # Combine heading, content, and spacy entities for full-text tokenization
            content = data.get('content', '')
            heading = data.get('heading', '')
            entities = " ".join(data.get('entities', []))
            
            # Simple whitespace tokenization as a base
            document_text = f"{heading} {content} {entities}".lower()
            corpus.append(document_text.split(" "))
            
        if corpus:
            self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_n: int = 1) -> list[dict]:
        """
        Uses BM25 to score nodes against the query, then expands the subgraph context.
        """
        if not self.bm25:
            return []
            
        tokenized_query = query.lower().split(" ")
        
        # Get raw node data scores
        top_node_contents = self.bm25.get_top_n(tokenized_query, self.kg.graph.nodes(data=True), n=top_n)
        
        results = []
        for node_id, data in top_node_contents:
            expanded_context = self._expand_context(node_id)
            results.append({
                "anchor_node": data,
                "pedagogical_context": expanded_context
            })
            
        return results

    def _expand_context(self, anchor_node_id: str) -> list[dict]:
        """
        Retrieves the pedagogical context sub-graph: Ancestors + Anchor + Children
        """
        context_nodes = []
        
        # Get Ancestors (path to root)
        try:
            ancestors = nx.ancestors(self.kg.graph, anchor_node_id)
            for anc_id in ancestors:
                context_nodes.append(self.kg.graph.nodes[anc_id])
        except nx.NetworkXError:
            pass

        # Add Anchor
        context_nodes.append(self.kg.graph.nodes[anchor_node_id])
        
        # Get Children (depth 1)
        try:
            children = list(self.kg.graph.successors(anchor_node_id))
            for child_id in children:
                context_nodes.append(self.kg.graph.nodes[child_id])
        except nx.NetworkXError:
            pass
            
        return context_nodes
