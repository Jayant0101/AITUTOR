import re
import os
import logging
from collections import deque
from collections import Counter
from math import log

import networkx as nx

logger = logging.getLogger(__name__)
try:
    import spacy
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    spacy = None
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
    STOPWORDS = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "what",
        "how",
        "why",
        "when",
        "where",
        "who",
        "does",
        "do",
        "did",
        "can",
        "could",
        "should",
        "would",
        "please",
        "explain",
        "tell",
        "about",
        "for",
        "to",
        "of",
        "and",
        "in",
        "on",
        "with",
    }
    SYNONYMS = {
        "rag": "retrieval",
        "retrieve": "retrieval",
        "retrieving": "retrieval",
        "graphs": "graph",
        "knowledge-graph": "graph",
        "rerank": "reranking",
        "ranker": "reranking",
        "llm": "language_model",
        "model": "language_model",
        "student": "learner",
        "learning": "learner",
        "concept map": "graph",
        "topic graph": "graph",
        "keyword search": "bm25",
    }
    SOURCE_TRUST_SCORES = {
        "docs": 1.0,
        "educational": 0.8,
        "blog": 0.5,
        "web": 0.3, # General web as a fallback
        "unknown": 0.1,
    }

    def __init__(self, knowledge_graph) -> None:
        self.kg = knowledge_graph
        self.bm25: BM25Okapi | None = None
        self.node_ids: list[str] = []
        self.node_meta: dict[str, dict] = {}
        self.alias_map: dict[str, set[str]] = {}
        self.title_token_index: dict[str, set[str]] = {}
        self.node_cluster_map: dict[str, str] = {}
        if spacy is None:
            self.nlp = None
        else:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                self.nlp = None
        self.w_bm25 = float(os.getenv("RERANK_W_BM25", "0.36"))
        self.w_phrase = float(os.getenv("RERANK_W_PHRASE", "0.26"))
        self.w_title = float(os.getenv("RERANK_W_TITLE", "0.18"))
        self.w_entity = float(os.getenv("RERANK_W_ENTITY", "0.15"))
        self.w_graph = float(os.getenv("RERANK_W_GRAPH", "0.05"))
        self.diversity_penalty_weight = float(os.getenv("RERANK_DIVERSITY_PENALTY", "0.22"))
        self.mmr_lambda = float(os.getenv("RERANK_MMR_LAMBDA", "0.6"))
        self.candidate_pool_size = int(os.getenv("RETRIEVAL_CANDIDATE_POOL", "15"))
        self.min_selection_confidence = float(os.getenv("RETRIEVAL_MIN_CONFIDENCE", "0.20"))
        self.rank3_gap_ratio = float(os.getenv("RETRIEVAL_RANK3_GAP_RATIO", "0.80"))
        self.w_concept_coverage = float(os.getenv("RERANK_W_CONCEPT_COVERAGE", "0.12"))
        self.w_multi_concept = float(os.getenv("RERANK_W_MULTI_CONCEPT", "0.08"))
        self.w_relationship = float(os.getenv("RERANK_W_RELATIONSHIP", "0.07"))
        self.fullsystem_candidate_floor = int(os.getenv("RETRIEVAL_FULLSYSTEM_POOL_FLOOR", "24"))
        self._build_index()

    def _tokenize(self, text: str) -> list[str]:
        # Add debug logging
        logger.debug(f"Tokenizing text: '{text}'")
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        logger.debug(f"Tokens: {tokens}")
        return [token for token in tokens if token]

    def _normalize_tokens(self, tokens: list[str]) -> list[str]:
        # Add debug logging
        logger.debug(f"Normalizing tokens: {tokens}")
        normalized = []
        for token in tokens:
            if token in self.STOPWORDS or len(token) < 3:
                continue
            normalized.append(self.SYNONYMS.get(token, token))
        logger.debug(f"Normalized tokens: {normalized}")
        return normalized

    def _extract_query_phrases(self, query: str) -> list[str]:
        query = query.strip()
        if not query:
            return []
        phrases: list[str] = []
        if self.nlp is not None:
            try:
                doc = self.nlp(query)
                for chunk in doc.noun_chunks:
                    phrase = " ".join(self._normalize_tokens(self._tokenize(chunk.text)))
                    if len(phrase) >= 4:
                        phrases.append(phrase)
            except Exception:
                phrases = []

        if not phrases:
            # fallback: light bigram/trigram phrases from normalized tokens
            toks = self._normalize_tokens(self._tokenize(query))
            for size in (3, 2):
                for idx in range(0, max(len(toks) - size + 1, 0)):
                    phrase = " ".join(toks[idx : idx + size]).strip()
                    if phrase:
                        phrases.append(phrase)

        seen = set()
        unique = []
        for phrase in phrases:
            mapped = " ".join(self.SYNONYMS.get(tok, tok) for tok in phrase.split())
            if mapped and mapped not in seen:
                seen.add(mapped)
                unique.append(mapped)
        return unique[:8]

    def _extract_query_entities(self, query: str) -> list[str]:
        entities: list[str] = []
        if self.nlp is not None:
            try:
                doc = self.nlp(query)
                for ent in doc.ents:
                    norm = " ".join(self._normalize_tokens(self._tokenize(ent.text)))
                    if norm:
                        entities.append(norm)
            except Exception:
                entities = []
        return list(dict.fromkeys(entities))[:6]

    def _detect_query_intent(self, query: str) -> str:
        lowered = query.lower()
        if "compare" in lowered or "difference" in lowered or "vs" in lowered:
            return "comparison"
        if "how" in lowered or "why" in lowered:
            return "explanation"
        return "definition"

    def _build_index(self) -> None:
        corpus: list[list[str]] = []
        self.node_ids = []
        self.node_meta = {}
        self.alias_map = {}
        self.title_token_index = {}
        self.node_cluster_map = {}

        for node_id, data in self.kg.graph.nodes(data=True):
            self.node_ids.append(node_id)
            content = data.get("content", "")
            heading = data.get("heading", "")
            entities = " ".join(data.get("entities", []))
            keywords = " ".join(data.get("keywords", []))
            source = data.get("source", "")
            document_text = f"{heading} {content} {entities} {keywords} {source}"
            tokens = self._normalize_tokens(self._tokenize(document_text))
            corpus.append(tokens)

            heading_tokens = self._normalize_tokens(self._tokenize(heading))
            keyword_tokens = self._normalize_tokens(self._tokenize(keywords))
            entity_tokens = self._normalize_tokens(self._tokenize(entities))
            self.node_meta[node_id] = {
                "heading_tokens": heading_tokens,
                "keyword_tokens": keyword_tokens,
                "entity_tokens": entity_tokens,
                "heading_text": " ".join(heading_tokens),
                "doc_text": document_text.lower(),
            }
            self.title_token_index[node_id] = set(heading_tokens)
            self.node_cluster_map[node_id] = self._infer_cluster_id(
                node_id=node_id,
                heading_tokens=heading_tokens,
                source=str(data.get("source", "")),
                level=int(data.get("level", 0)),
            )

            for token in set(heading_tokens + keyword_tokens + entity_tokens):
                self.alias_map.setdefault(token, set()).add(node_id)

        self.bm25 = BM25Okapi(corpus) if corpus else None
        # Add debug logging
        if self.bm25:
            logger.info("BM25 index built successfully.")
            logger.info(f"Corpus size: {self.bm25.corpus_size}")
            # logger.debug(f"Document frequencies: {self.bm25.doc_freq}")
        else:
            logger.error("BM25 index build failed.")

    def rebuild(self) -> None:
        self._build_index()

    def search(
        self,
        query: str,
        top_n: int = 3,
        expand_depth: int = 1,
        use_rerank: bool = True,
    ) -> list[dict]:
        if not self.bm25 or not self.node_ids:
            return []

        # Add debug logging
        logger.debug(f"Original query: '{query}'")
        base_tokens = self._normalize_tokens(self._tokenize(query))
        logger.debug(f"Base tokens for search: {base_tokens}")
        query_phrases = self._extract_query_phrases(query)
        query_entities = self._extract_query_entities(query)
        query_intent = self._detect_query_intent(query)
        sub_intents = self._extract_sub_intents(query, base_tokens, query_phrases)
        hard_negatives = self._identify_hard_negatives(query_tokens=base_tokens, query_phrases=query_phrases)
        tokenized_query = self._expand_query(base_tokens)
        if not tokenized_query:
            return []
        
        # Add debug logging
        logger.debug(f"Expanded tokenized query: {tokenized_query}")

        scores = self.bm25.get_scores(tokenized_query)
        # Add debug logging
        logger.debug(f"BM25 scores: {scores}")
        ranked_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)
        # Add debug logging
        logger.debug(f"Ranked indices: {ranked_indices}")
        
        # Logging top 5 results for debug
        logger.debug("--- Top 5 BM25 Ranked Documents ---")
        for i in range(min(5, len(ranked_indices))):
            idx = ranked_indices[i]
            node_id = self.node_ids[idx]
            node_data = self.kg.graph.nodes[node_id]
            logger.debug(f"Rank {i+1}: Node ID: {node_id}, Score: {scores[idx]}")
            logger.debug(f"  Heading: {node_data.get('heading')}")
            logger.debug(f"  Content: {node_data.get('content', '')[:100]}...")
        logger.debug("-------------------------------------")

        candidate_indices = self._build_candidate_pool(
            ranked_indices=ranked_indices,
            top_n=max(top_n, 1),
            query_tokens=base_tokens,
            sub_intents=sub_intents,
            hard_negatives=hard_negatives,
            use_rerank=use_rerank,
        )
        if use_rerank:
            reranked_indices = self._rerank_candidates(
                candidate_indices=candidate_indices,
                bm25_scores=scores,
                query_tokens=base_tokens,
                query_phrases=query_phrases,
                query_entities=query_entities,
                query_intent=query_intent,
            )
        else:
            reranked_indices = candidate_indices

        # `scores` can be a NumPy array; avoid truthiness checks like `if scores`.
        if scores is None or len(scores) == 0:
            max_score = 1.0
            min_score = 0.0
        else:
            try:
                # NumPy arrays support `.max()`/`.min()` safely.
                max_score = float(scores.max())  # type: ignore[attr-defined]
                min_score = float(scores.min())  # type: ignore[attr-defined]
            except Exception:
                max_score = max(scores)
                min_score = min(scores)
        span = (max_score - min_score) or 1.0

        results: list[dict] = []
        depth = max(1, min(expand_depth, 2))
        candidates: list[dict] = []
        for idx in reranked_indices:
            node_id = self.node_ids[idx]
            node_data = dict(self.kg.graph.nodes[node_id])
            if use_rerank:
                confidence = float(node_data.get("_combined_score", 0.0))
                ranking_features = node_data.get("_ranking_features", {})
                node_hard_negative = node_id in hard_negatives
                has_direct_alias_match = any(
                    node_id in self.alias_map.get(token, set()) for token in base_tokens
                )
                no_phrase = float(ranking_features.get("phrase_match_score", 0.0)) <= 0.0
                no_entity = float(ranking_features.get("entity_overlap", 0.0)) <= 0.0
                if node_hard_negative and not has_direct_alias_match:
                    confidence -= 0.12
                    ranking_features["hard_negative_penalty"] = 0.12
                if no_phrase and no_entity:
                    confidence -= 0.06
                    ranking_features["weak_match_penalty"] = 0.06
                confidence = max(0.0, confidence)
            else:
                bm25_norm = (scores[idx] - min_score) / span
                confidence = max(0.2, bm25_norm)
                ranking_features = {
                    "bm25_norm": round(bm25_norm, 4),
                    "ranking_mode": "bm25_only",
                }
            if confidence < 0.2:
                continue
            context = self._expand_context(
                anchor_node_id=node_id,
                depth=depth,
                query_tokens=base_tokens,
            )
            candidates.append(
                {
                    "anchor_node_id": node_id,
                    "anchor_node": node_data,
                    "score": float(scores[idx]),
                    "confidence": confidence,
                    "ranking_features": ranking_features,
                    "pedagogical_context": context,
                }
            )

        candidates = self.rerank_by_source_credibility(candidates)
        results = self._select_diverse_top_k(candidates, top_n=max(top_n, 1))
        results = self._apply_threshold_filters(results, requested_top_n=max(top_n, 1))
        if results:
            results[0]["candidate_pool_node_ids"] = [self.node_ids[idx] for idx in candidate_indices]
            results[0]["query_sub_intents"] = sub_intents
            results[0]["hard_negative_node_ids"] = sorted(hard_negatives)
            results[0]["query_intent"] = query_intent
            results[0]["query_entities"] = query_entities
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
                edge = self.kg.graph.get_edge_data(node_id, child_id) or {}
                edge_kind = edge.get("kind", "hierarchy")
                edge_weight = float(edge.get("weight", 1.0))
                if edge_kind not in {"hierarchy", "prerequisite", "related"}:
                    continue
                if edge_weight < 0.35:
                    continue
                child_data = self.kg.graph.nodes[child_id]
                child_heading = self._tokenize(child_data.get("heading", ""))
                child_keywords = self._tokenize(" ".join(child_data.get("keywords", [])))
                overlap = len(set(child_heading + child_keywords).intersection(query_tokens or []))
                # Tighten expansion: weak edge + no lexical evidence => skip
                if edge_weight < 0.6 and overlap == 0:
                    continue
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
        return self._normalize_tokens(list(expanded))

    def _rerank_candidates(
        self,
        candidate_indices: list[int],
        bm25_scores: list[float],
        query_tokens: list[str],
        query_phrases: list[str],
        query_entities: list[str],
        query_intent: str,
    ) -> list[int]:
        if not candidate_indices:
            return []
        max_score = max(bm25_scores[idx] for idx in candidate_indices) or 1.0
        min_score = min(bm25_scores[idx] for idx in candidate_indices)
        span = max_score - min_score or 1.0
        direct_match_nodes = {
            node_id for token in query_tokens for node_id in self.alias_map.get(token, set())
        }
        undirected = self.kg.graph.to_undirected(as_view=True)

        def combined(idx: int) -> float:
            node_id = self.node_ids[idx]
            meta = self.node_meta.get(node_id, {})
            heading_tokens = set(meta.get("heading_tokens", []))
            keyword_tokens = set(meta.get("keyword_tokens", []))
            entity_tokens = set(meta.get("entity_tokens", []))
            all_tokens = heading_tokens | keyword_tokens | entity_tokens
            query_token_set = set(query_tokens)

            heading_match = len(heading_tokens.intersection(query_token_set)) / max(
                len(query_token_set), 1
            )
            entity_overlap = len(entity_tokens.intersection(query_token_set)) / max(
                len(query_token_set), 1
            )
            lexical_overlap = len(all_tokens.intersection(query_token_set)) / max(
                len(query_token_set), 1
            )
            bm25_norm = (bm25_scores[idx] - min_score) / span
            bm25_scaled = log(1 + (9 * max(0.0, min(1.0, bm25_norm)))) / log(10)

            heading_text = meta.get("heading_text", "")
            doc_text = meta.get("doc_text", "")
            phrase_hits = 0
            for phrase in query_phrases:
                if phrase in heading_text or phrase in doc_text:
                    phrase_hits += 1
            phrase_match_score = phrase_hits / max(len(query_phrases), 1) if query_phrases else 0.0
            phrase_match_score = min(0.85, phrase_match_score)

            node_title_match = 0.0
            if heading_text:
                if heading_text in " ".join(query_tokens):
                    node_title_match = 1.0
                elif query_token_set.intersection(heading_tokens):
                    overlap_ratio = len(query_token_set.intersection(heading_tokens)) / max(
                        len(heading_tokens), 1
                    )
                    node_title_match = max(node_title_match, min(0.9, overlap_ratio + 0.2))
                if any(phrase and phrase in heading_text for phrase in query_phrases):
                    node_title_match = max(node_title_match, 0.95)
            node_title_match = min(0.9, node_title_match)
            entity_overlap = min(0.85, entity_overlap)

            candidate_concepts = set(heading_tokens) | keyword_tokens | entity_tokens
            query_concepts = set(query_tokens)
            for phrase in query_phrases:
                query_concepts.update(phrase.split())
            for ent in query_entities:
                query_concepts.update(ent.split())

            concept_hits = len(candidate_concepts.intersection(query_concepts))
            concept_coverage_score = concept_hits / max(len(query_concepts), 1)

            multi_concept_bonus = 0.0
            if concept_hits >= 2:
                multi_concept_bonus = min(1.0, (concept_hits - 1) / 3.0)

            relationship_score = 0.0
            if len(query_concepts) >= 2:
                matched = list(candidate_concepts.intersection(query_concepts))
                if len(matched) >= 2:
                    relationship_score = 1.0
                elif len(matched) == 1 and query_intent == "definition":
                    relationship_score = 0.35
                elif len(matched) == 1 and query_intent == "explanation":
                    relationship_score = 0.2

            # small intent-aware shaping
            if query_intent == "comparison" and len(matched) >= 2:
                relationship_score = max(relationship_score, 0.9)
            elif query_intent == "explanation" and phrase_match_score > 0:
                relationship_score = max(relationship_score, 0.45)

            graph_distance_penalty = 0.5
            if direct_match_nodes:
                best_dist = None
                for match_node in direct_match_nodes:
                    try:
                        dist = nx.shortest_path_length(undirected, source=node_id, target=match_node)
                    except Exception:
                        continue
                    best_dist = dist if best_dist is None else min(best_dist, dist)
                if best_dist is not None:
                    graph_distance_penalty = min(1.0, float(best_dist) / 4.0)

            # Configurable weighted sum with capped features and bm25 log-scaling.
            score = (
                self.w_bm25 * bm25_scaled
                + self.w_phrase * phrase_match_score
                + self.w_title * node_title_match
                + self.w_entity * entity_overlap
                + self.w_graph * (1.0 - graph_distance_penalty)
                + self.w_concept_coverage * concept_coverage_score
                + self.w_multi_concept * multi_concept_bonus
                + self.w_relationship * relationship_score
            )
            self.kg.graph.nodes[node_id]["_combined_score"] = score
            self.kg.graph.nodes[node_id]["_ranking_features"] = {
                "bm25_norm": round(bm25_norm, 4),
                "bm25_scaled": round(bm25_scaled, 4),
                "phrase_match_score": round(phrase_match_score, 4),
                "node_title_match": round(node_title_match, 4),
                "heading_match": round(heading_match, 4),
                "entity_overlap": round(entity_overlap, 4),
                "concept_coverage_score": round(concept_coverage_score, 4),
                "multi_concept_bonus": round(multi_concept_bonus, 4),
                "relationship_score": round(relationship_score, 4),
                "lexical_overlap": round(lexical_overlap, 4),
                "graph_distance_penalty": round(graph_distance_penalty, 4),
                "query_phrases": query_phrases,
                "query_entities": query_entities,
                "query_intent": query_intent,
            }
            return score

        return sorted(candidate_indices, key=combined, reverse=True)

    def _select_diverse_top_k(self, candidates: list[dict], top_n: int) -> list[dict]:
        if not candidates:
            return []
        selected: list[dict] = []
        remaining = list(candidates)
        mmr_lambda = max(0.0, min(1.0, self.mmr_lambda))
        selected_clusters: set[str] = set()
        while remaining and len(selected) < top_n:
            best_item = None
            best_score = float("-inf")
            for item in remaining:
                item_cluster = self._cluster_for_item(item)
                if item_cluster in selected_clusters:
                    # Hard diversity constraint: at most one node per cluster.
                    continue
                if self._is_near_duplicate(item, selected):
                    # Hard diversity constraint: no near-identical nodes.
                    continue
                relevance = float(item.get("confidence", 0.0))
                max_similarity = 0.0
                for chosen in selected:
                    max_similarity = max(max_similarity, self._candidate_similarity(item, chosen))

                # Maximal Marginal Relevance:
                # mmr = λ * relevance - (1-λ) * max_similarity
                mmr_score = (mmr_lambda * relevance) - ((1.0 - mmr_lambda) * max_similarity)
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item
            if not best_item:
                break
            selected.append(best_item)
            selected_clusters.add(self._cluster_for_item(best_item))
            remaining = [it for it in remaining if it.get("anchor_node_id") != best_item.get("anchor_node_id")]
        return selected

    def _candidate_similarity(self, left: dict, right: dict) -> float:
        left_anchor = left.get("anchor_node", {}) or {}
        right_anchor = right.get("anchor_node", {}) or {}

        left_heading_tokens = set(self._tokenize(left_anchor.get("heading", "")))
        right_heading_tokens = set(self._tokenize(right_anchor.get("heading", "")))
        intersection = len(left_heading_tokens.intersection(right_heading_tokens))
        union = len(left_heading_tokens.union(right_heading_tokens)) or 1
        heading_overlap = intersection / union

        left_parent = str(left_anchor.get("parent_id", ""))
        right_parent = str(right_anchor.get("parent_id", ""))
        shared_parent = 1.0 if left_parent and right_parent and left_parent == right_parent else 0.0

        left_source = str(left_anchor.get("source", ""))
        right_source = str(right_anchor.get("source", ""))
        shared_source = 1.0 if left_source and right_source and left_source == right_source else 0.0

        left_keywords = set(self._tokenize(" ".join(left_anchor.get("keywords", []) or [])))
        right_keywords = set(self._tokenize(" ".join(right_anchor.get("keywords", []) or [])))
        kw_intersection = len(left_keywords.intersection(right_keywords))
        kw_union = len(left_keywords.union(right_keywords)) or 1
        concept_similarity = kw_intersection / kw_union

        similarity = (
            0.45 * heading_overlap
            + 0.20 * shared_parent
            + 0.15 * shared_source
            + 0.20 * concept_similarity
        )
        return max(0.0, min(1.0, similarity))

    def _build_candidate_pool(
        self,
        ranked_indices: list[int],
        top_n: int,
        query_tokens: list[str],
        sub_intents: list[list[str]],
        hard_negatives: set[str],
        use_rerank: bool,
    ) -> list[int]:
        seed_size = max(10, min(self.candidate_pool_size, max(top_n * 6, 20)))
        seed_indices = ranked_indices[:seed_size]
        candidate_ids = {self.node_ids[idx] for idx in seed_indices}

        # Expand with graph neighbors and related concept nodes from lexical aliases.
        alias_nodes = {node_id for token in query_tokens for node_id in self.alias_map.get(token, set())}
        frontier = list(candidate_ids.union(alias_nodes))
        for node_id in frontier:
            if node_id not in self.kg.graph:
                continue
            for neighbor in self.kg.graph.predecessors(node_id):
                candidate_ids.add(neighbor)
            for neighbor in self.kg.graph.successors(node_id):
                candidate_ids.add(neighbor)

        # Multi-intent retrieval: ensure each sub-intent contributes candidates.
        if self.bm25:
            for intent_tokens in sub_intents:
                if not intent_tokens:
                    continue
                intent_scores = self.bm25.get_scores(intent_tokens)
                intent_ranked = sorted(
                    range(len(intent_scores)),
                    key=lambda idx: intent_scores[idx],
                    reverse=True,
                )[: max(5, top_n * 2)]
                for idx in intent_ranked:
                    candidate_ids.add(self.node_ids[idx])

        # Inject hard negatives explicitly to force ambiguity handling.
        for node_id in sorted(hard_negatives):
            candidate_ids.add(node_id)

        # Convert back to indices and keep a bounded but expanded pool.
        id_to_idx = {node_id: idx for idx, node_id in enumerate(self.node_ids)}
        candidate_indices = [id_to_idx[node_id] for node_id in candidate_ids if node_id in id_to_idx]
        candidate_indices.sort(key=lambda idx: ranked_indices.index(idx) if idx in ranked_indices else len(ranked_indices))
        upper = max(seed_size, self.fullsystem_candidate_floor if use_rerank else 18)
        return candidate_indices[:upper]

    def _extract_sub_intents(
        self,
        query: str,
        query_tokens: list[str],
        query_phrases: list[str],
    ) -> list[list[str]]:
        intents: list[list[str]] = []
        for phrase in query_phrases[:4]:
            tokens = self._normalize_tokens(self._tokenize(phrase))
            if tokens:
                intents.append(tokens)

        if " and " in query.lower():
            for part in query.lower().split(" and "):
                tokens = self._normalize_tokens(self._tokenize(part))
                if tokens:
                    intents.append(tokens)

        if query_tokens and len(query_tokens) >= 2:
            intents.append(query_tokens[: max(2, min(4, len(query_tokens)))])

        unique: list[list[str]] = []
        seen = set()
        for toks in intents:
            key = tuple(toks)
            if key not in seen:
                seen.add(key)
                unique.append(toks)
        return unique[:6]

    def _infer_cluster_id(
        self, node_id: str, heading_tokens: list[str], source: str, level: int
    ) -> str:
        if heading_tokens:
            topic = "_".join(heading_tokens[:2])
        else:
            topic = node_id[:6]
        return f"{source}|L{level}|{topic}"

    def _cluster_for_item(self, item: dict) -> str:
        node_id = item.get("anchor_node_id")
        if node_id and node_id in self.node_cluster_map:
            return self.node_cluster_map[node_id]
        heading_tokens = self._tokenize((item.get("anchor_node", {}) or {}).get("heading", ""))
        source = str((item.get("anchor_node", {}) or {}).get("source", "unknown"))
        return self._infer_cluster_id(node_id or "unknown", heading_tokens, source, 0)

    def _is_near_duplicate(self, item: dict, selected: list[dict]) -> bool:
        if not selected:
            return False
        item_heading_tokens = set(
            self._tokenize((item.get("anchor_node", {}) or {}).get("heading", ""))
        )
        for chosen in selected:
            chosen_tokens = set(
                self._tokenize((chosen.get("anchor_node", {}) or {}).get("heading", ""))
            )
            inter = len(item_heading_tokens.intersection(chosen_tokens))
            union = len(item_heading_tokens.union(chosen_tokens)) or 1
            if inter / union >= 0.75:
                return True
        return False

    def _identify_hard_negatives(self, query_tokens: list[str], query_phrases: list[str]) -> set[str]:
        hard_negatives: set[str] = set()
        query_set = set(query_tokens)
        query_phrase_text = " ".join(query_phrases)
        for node_id, meta in self.node_meta.items():
            heading_tokens = set(meta.get("heading_tokens", []))
            entity_tokens = set(meta.get("entity_tokens", []))
            overlap = len(query_set.intersection(heading_tokens))
            entity_overlap = len(query_set.intersection(entity_tokens))
            heading_text = str(meta.get("heading_text", ""))
            phrase_hit = bool(query_phrase_text and any(p in heading_text for p in query_phrases))
            # Hard negative heuristic: weak lexical coincidence but no strong phrase/entity evidence.
            if overlap == 1 and entity_overlap == 0 and not phrase_hit and len(query_set) >= 2:
                hard_negatives.add(node_id)
        return hard_negatives

    def _apply_threshold_filters(self, selected: list[dict], requested_top_n: int) -> list[dict]:
        if not selected:
            return []
        min_conf = max(0.0, min(1.0, self.min_selection_confidence))
        filtered = [item for item in selected if float(item.get("confidence", 0.0)) >= min_conf]
        if not filtered:
            filtered = selected[:1]

        # Dynamic top-k (2 or 3): if third rank confidence drops sharply, drop it.
        if len(filtered) >= 3:
            c2 = float(filtered[1].get("confidence", 0.0))
            c3 = float(filtered[2].get("confidence", 0.0))
            gap = c2 - c3
            ratio = gap / max(c2, 1e-6)
            if ratio >= self.rank3_gap_ratio:
                filtered = filtered[:2]

        return filtered[:requested_top_n]

    def _filter_context(self, context_nodes: list[dict], query_tokens: list[str]) -> list[dict]:
        if not query_tokens:
            return context_nodes[:5]
        filtered: list[dict] = []
        seen_headings: set[str] = set()
        for node in context_nodes:
            heading = self._tokenize(node.get("heading", ""))
            keywords = self._tokenize(" ".join(node.get("keywords", [])))
            heading_key = " ".join(heading[:6])
            if heading_key and heading_key in seen_headings:
                continue
            match_ratio = len(set(heading + keywords).intersection(query_tokens)) / max(
                len(set(query_tokens)), 1
            )
            confidence = float(node.get("_combined_score", 0.0))
            if match_ratio >= 0.2 or confidence >= 0.25:
                filtered.append(node)
                if heading_key:
                    seen_headings.add(heading_key)
        return filtered[:5] if filtered else context_nodes[:3]

    def rerank_by_source_credibility(self, results: list[dict]) -> list[dict]:
        for result in results:
            source_type = result.get("anchor_node", {}).get("source_type", "unknown")
            trust_score = self.SOURCE_TRUST_SCORES.get(source_type, self.SOURCE_TRUST_SCORES["unknown"])
            result["confidence"] *= trust_score
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results
