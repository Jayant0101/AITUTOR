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
        self.node_meta: dict[str, dict] = {}
        self.alias_map: dict[str, set[str]] = {}
        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return [token for token in tokens if token]

    def _build_index(self) -> None:
        corpus: list[list[str]] = []
        self.node_ids = []
        self.node_meta = {}
        self.alias_map = {}

        for node_id, data in self.kg.graph.nodes(data=True):
            self.node_ids.append(node_id)
            content = data.get("content", "")
            heading = data.get("heading", "")
            entities = " ".join(data.get("entities", []))
            keywords = " ".join(data.get("keywords", []))
            source = data.get("source", "")
            document_text = f"{heading} {content} {entities} {keywords} {source}"
            tokens = self._tokenize(document_text)
            corpus.append(tokens)

            heading_tokens = self._tokenize(heading)
            keyword_tokens = self._tokenize(keywords)
            entity_tokens = self._tokenize(entities)
            self.node_meta[node_id] = {
                "heading_tokens": heading_tokens,
                "keyword_tokens": keyword_tokens,
                "entity_tokens": entity_tokens,
            }

            for token in set(heading_tokens + keyword_tokens + entity_tokens):
                self.alias_map.setdefault(token, set()).add(node_id)

        self.bm25 = BM25Okapi(corpus) if corpus else None

    def rebuild(self) -> None:
        self._build_index()

    def search(self, query: str, top_n: int = 3, expand_depth: int = 1) -> list[dict]:
        if not self.bm25 or not self.node_ids:
            return []

        base_tokens = self._tokenize(query)
        tokenized_query = self._expand_query(base_tokens)
        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)
        ranked_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)
        candidate_indices = ranked_indices[: max(top_n * 4, 6)]
        reranked_indices = self._rerank_candidates(candidate_indices, scores, base_tokens)

        results: list[dict] = []
        for idx in reranked_indices[: max(top_n, 1)]:
            node_id = self.node_ids[idx]
            node_data = dict(self.kg.graph.nodes[node_id])
            context = self._expand_context(
                anchor_node_id=node_id,
                depth=expand_depth,
                query_tokens=base_tokens,
            )
            results.append(
                {
                    "anchor_node_id": node_id,
                    "anchor_node": node_data,
                    "score": float(scores[idx]),
                    "pedagogical_context": context,
                }
            )
        return results

    def _expand_context(
        self, anchor_node_id: str, depth: int = 1, query_tokens: list[str] | None = None
    ) -> list[dict]:
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
        return self._filter_context(context_nodes, query_tokens or [])

    def _expand_query(self, tokens: list[str]) -> list[str]:
        expanded = set(tokens)
        for token in tokens:
            for node_id in self.alias_map.get(token, set()):
                meta = self.node_meta.get(node_id, {})
                expanded.update(meta.get("heading_tokens", [])[:3])
                expanded.update(meta.get("keyword_tokens", [])[:3])
        return list(expanded)

    def _rerank_candidates(
        self, candidate_indices: list[int], bm25_scores: list[float], query_tokens: list[str]
    ) -> list[int]:
        if not candidate_indices:
            return []
        max_score = max(bm25_scores[idx] for idx in candidate_indices) or 1.0
        min_score = min(bm25_scores[idx] for idx in candidate_indices)
        span = max_score - min_score or 1.0

        def combined(idx: int) -> float:
            node_id = self.node_ids[idx]
            meta = self.node_meta.get(node_id, {})
            tokens = set(
                meta.get("heading_tokens", [])
                + meta.get("keyword_tokens", [])
                + meta.get("entity_tokens", [])
            )
            overlap = (
                len(tokens.intersection(query_tokens)) / max(len(set(query_tokens)), 1)
            )
            bm25_norm = (bm25_scores[idx] - min_score) / span
            return 0.7 * bm25_norm + 0.3 * overlap

        return sorted(candidate_indices, key=combined, reverse=True)

    def _filter_context(self, context_nodes: list[dict], query_tokens: list[str]) -> list[dict]:
        if not query_tokens:
            return context_nodes[:12]
        filtered = []
        for node in context_nodes:
            heading = self._tokenize(node.get("heading", ""))
            keywords = self._tokenize(" ".join(node.get("keywords", [])))
            if set(heading + keywords).intersection(query_tokens):
                filtered.append(node)
        return filtered[:12] if filtered else context_nodes[:8]
