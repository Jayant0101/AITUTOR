import re
from collections import deque
from collections import Counter
from math import log

import networkx as nx
try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - fallback for offline environments
    class BM25Okapi:  # type: ignore[override]
        def __init__(self, corpus: list[list[str]]) -> None:
            self.corpus = corpus
            self.k1 = 1.5
            self.b = 0.75
            self.doc_len = [len(doc) for doc in corpus]
            self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if corpus else 0.0
            self.doc_freq: dict[str, int] = {}
            self.term_freqs: list[Counter[str]] = []

            for doc in corpus:
                tf = Counter(doc)
                self.term_freqs.append(tf)
                for term in tf:
                    self.doc_freq[term] = self.doc_freq.get(term, 0) + 1

            self.corpus_size = len(corpus)

        def get_scores(self, query_tokens: list[str]) -> list[float]:
            if not self.corpus:
                return []
            scores = [0.0] * len(self.corpus)
            for token in query_tokens:
                df = self.doc_freq.get(token, 0)
                if df == 0:
                    continue
                idf = log((self.corpus_size - df + 0.5) / (df + 0.5) + 1)
                for idx, tf in enumerate(self.term_freqs):
                    freq = tf.get(token, 0)
                    if freq == 0:
                        continue
                    dl = self.doc_len[idx]
                    denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                    scores[idx] += idf * (freq * (self.k1 + 1) / denom)
            return scores


class RetrievalEngine:
    def __init__(self, knowledge_graph) -> None:
        self.kg = knowledge_graph
        self.bm25: BM25Okapi | None = None
        self.node_ids: list[str] = []
        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return [token for token in tokens if token]

    def _build_index(self) -> None:
        corpus: list[list[str]] = []
        self.node_ids = []

        for node_id, data in self.kg.graph.nodes(data=True):
            self.node_ids.append(node_id)
            content = data.get("content", "")
            heading = data.get("heading", "")
            entities = " ".join(data.get("entities", []))
            keywords = " ".join(data.get("keywords", []))
            source = data.get("source", "")
            document_text = f"{heading} {content} {entities} {keywords} {source}"
            corpus.append(self._tokenize(document_text))

        self.bm25 = BM25Okapi(corpus) if corpus else None

    def rebuild(self) -> None:
        self._build_index()

    def search(self, query: str, top_n: int = 3, expand_depth: int = 1) -> list[dict]:
        if not self.bm25 or not self.node_ids:
            return []

        tokenized_query = self._tokenize(query)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda idx: scores[idx],
            reverse=True,
        )

        results: list[dict] = []
        for idx in ranked_indices[: max(top_n, 1)]:
            node_id = self.node_ids[idx]
            node_data = dict(self.kg.graph.nodes[node_id])
            context = self._expand_context(anchor_node_id=node_id, depth=expand_depth)
            results.append(
                {
                    "anchor_node_id": node_id,
                    "anchor_node": node_data,
                    "score": float(scores[idx]),
                    "pedagogical_context": context,
                }
            )
        return results

    def _expand_context(self, anchor_node_id: str, depth: int = 1) -> list[dict]:
        if anchor_node_id not in self.kg.graph:
            return []

        context_ids: list[str] = []
        seen_ids: set[str] = set()

        ancestors = sorted(
            nx.ancestors(self.kg.graph, anchor_node_id),
            key=lambda node_id: (
                int(self.kg.graph.nodes[node_id].get("level", 0)),
                self.kg.graph.nodes[node_id].get("heading", ""),
            ),
        )
        for node_id in ancestors:
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                context_ids.append(node_id)

        if anchor_node_id not in seen_ids:
            seen_ids.add(anchor_node_id)
            context_ids.append(anchor_node_id)

        queue: deque[tuple[str, int]] = deque([(anchor_node_id, 0)])
        while queue:
            node_id, node_depth = queue.popleft()
            if node_depth >= depth:
                continue
            for child_id in self.kg.graph.successors(node_id):
                if child_id not in seen_ids:
                    seen_ids.add(child_id)
                    context_ids.append(child_id)
                queue.append((child_id, node_depth + 1))

        context_nodes: list[dict] = []
        for node_id in context_ids:
            node_record = dict(self.kg.graph.nodes[node_id])
            node_record["id"] = node_id
            context_nodes.append(node_record)
        return context_nodes
