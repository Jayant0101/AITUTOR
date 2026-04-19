from __future__ import annotations

import os
import re
from pathlib import Path

from app.graph.graph_builder import KnowledgeGraph
from app.ingestion.ingestion import MarkdownParser
from app.retrieval.retrieval import RetrievalEngine
from app.learner.learner_tracker import LearnerTracker
from app.teaching.teaching_agent import TeachingAgent
from app.pipeline import apply_hybrid_retrieval

from app.debug_log import debug_log


class LearningAssistantService:
    def __init__(self, data_dir: str, db_path: str) -> None:
        self.data_dir = Path(data_dir)
        self.db_path = db_path
        self.parser = MarkdownParser()
        self.knowledge_graph = KnowledgeGraph()
        self.retrieval: RetrievalEngine | None = None
        self.learner = LearnerTracker(db_path=db_path)
        self.teacher = TeachingAgent()

    def initialize(self) -> None:
        # Idempotency guard: tests and startup events may both call initialize.
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Ensure database parent directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        self.learner.initialize_schema()
        self._ensure_seed_content()
        self.load_knowledge_base()

    def _ensure_seed_content(self) -> None:
        has_markdown = any(self.data_dir.rglob("*.md"))
        if has_markdown:
            return

        seed_path = self.data_dir / "sample_course.md"
        seed_path.write_text(
            "\n".join(
                [
                    "# Intro to Learning Systems",
                    "A learning system should adapt explanations based on learner progress.",
                    "",
                    "## Retrieval",
                    "Vectorless retrieval can use BM25 to rank text chunks by lexical relevance.",
                    "",
                    "## Knowledge Graph",
                    "A graph stores concept hierarchy so prerequisite topics can be expanded.",
                    "",
                    "## Learner Model",
                    "Mastery scores should improve with correct answers and decay on repeated errors.",
                    "",
                    "## Teaching Strategy",
                    "Socratic tutoring asks guided questions rather than only giving direct answers.",
                ]
            ),
            encoding="utf-8",
        )

    def load_knowledge_base(self, data_dir: str | None = None) -> dict:
        target_dir = Path(data_dir) if data_dir else self.data_dir
        chunks = self.parser.parse_directory(str(target_dir))
        self.knowledge_graph.build_from_chunks(chunks)
        self.retrieval = RetrievalEngine(self.knowledge_graph)

        return {
            "chunks_loaded": len(chunks),
            "nodes": self.knowledge_graph.graph.number_of_nodes(),
            "edges": self.knowledge_graph.graph.number_of_edges(),
            "data_dir": str(target_dir),
        }

    # ── Retrieval quality gate ──────────────────────────────────────────────
    # After all retrieval stages, check if we have high-enough context to
    # generate a grounded answer. If not, return a structured no_data
    # response instead of hallucinating.
    _NO_DATA_CONFIDENCE_THRESHOLD = 0.25

    def _is_retrieval_sufficient(self, retrieval_results: list[dict]) -> bool:
        """Return True when at least one retrieved item clears the confidence bar."""
        if not retrieval_results:
            return False
        max_conf = max(
            float(item.get("confidence", 0.0)) for item in retrieval_results
        )
        return max_conf >= self._NO_DATA_CONFIDENCE_THRESHOLD

    async def answer_query_stream(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        mode: str = "socratic",
        attachments: list[dict] | None = None,
        history: list[dict] | None = None,
    ):
        """Streaming version of answer_query."""
        self.learner.ensure_user(user_id)
        
        retrieval_results = (
            self.retrieval.search(query=query, top_n=max(top_k, 1), expand_depth=1)
            if self.retrieval
            else []
        )
        retrieval_results = self._select_high_quality_context(retrieval_results, requested_k=top_k)

        if attachments:
            retrieval_results = self._inject_attachment_context(
                retrieval_results=retrieval_results, attachments=attachments
            )

        retrieval_results = apply_hybrid_retrieval(query, retrieval_results, top_k=top_k)

        if not self._is_retrieval_sufficient(retrieval_results):
            yield "No relevant documents found. Please upload a document to proceed."
            return

        node_ids = self._collect_node_ids(retrieval_results)
        mastery_by_node = self.learner.get_mastery_by_node(user_id=user_id, node_ids=node_ids)

        async for chunk in self.teacher.generate_stream(
            query=query,
            retrieval_results=retrieval_results,
            mastery_by_node=mastery_by_node,
            mode=mode,
            history=history,
        ):
            yield chunk

    def answer_query(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        mode: str = "socratic",
        attachments: list[dict] | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        start_time = time.time()
        self.learner.ensure_user(user_id)
        
        try:
            retrieval_results = (
                self.retrieval.search(query=query, top_n=max(top_k, 1), expand_depth=1)
                if self.retrieval
                else []
            )
            retrieval_results = self._select_high_quality_context(retrieval_results, requested_k=top_k)

            if attachments:
                retrieval_results = self._inject_attachment_context(
                    retrieval_results=retrieval_results, attachments=attachments
                )

            # Additive upgrade: local-first with verified web fallback.
            retrieval_results = apply_hybrid_retrieval(
                query, retrieval_results, top_k=top_k
            )

            # Catch Tavily failure dict
            if isinstance(retrieval_results, dict) and retrieval_results.get("status") == "error":
                self.learner.track_metric("llm_latency", time.time() - start_time, {"status": "error", "error": "retrieval_failed"})
                return retrieval_results

            # ── Confidence gate ─────────────────────────────────────────────────
            # If we still have no usable context (after attachments + web fallback)
            # do NOT call the LLM. Return a structured no_data response instead.
            if not self._is_retrieval_sufficient(retrieval_results):
                self.learner.track_metric("llm_latency", time.time() - start_time, {"status": "no_data"})
                return {
                    "status": "no_data",
                    "message": "No relevant documents found. Please upload a document to proceed.",
                    "action": "upload_required",
                }
            # ────────────────────────────────────────────────────────────────────

            node_ids = self._collect_node_ids(retrieval_results)
            mastery_by_node = self.learner.get_mastery_by_node(user_id=user_id, node_ids=node_ids)

            debug_log(
                hypothesisId="C",
                message="answer_query_context_ready",
                data={
                    "retrieval_results_len": len(retrieval_results),
                    "node_ids_len": len(node_ids),
                    "mastery_by_node_len": len(mastery_by_node),
                    "attachments_present": bool(attachments),
                    "mode": mode,
                },
            )
            teaching_payload = self.teacher.generate(
                query=query,
                retrieval_results=retrieval_results,
                mastery_by_node=mastery_by_node,
                mode=mode,
                history=history,
            )

            # Determine sources list from citations for the success response.
            sources = [
                c.get("source", c.get("heading", "unknown"))
                for c in teaching_payload.get("citations", [])
            ]

            # ── Response validation ──
            if not teaching_payload.get("text") or not teaching_payload.get("text").strip():
                self.learner.track_metric("llm_latency", time.time() - start_time, {"status": "error", "error": "empty_response"})
                return {
                    "status": "error",
                    "message": "Response generation failed. Please try again."
                }
                
            if not sources:
                self.learner.track_metric("llm_latency", time.time() - start_time, {"status": "error", "error": "no_citations"})
                return {
                    "status": "error",
                    "message": "Response generation failed to provide citations. Try uploading a document."
                }

            latency = time.time() - start_time
            self.learner.track_metric("llm_latency", latency, {"status": "success"})
            
            return {
                "status": "success",
                "query": query,
                "mode": mode,
                "result": teaching_payload,
                "retrieval": retrieval_results,
                "sources": sources,
            }
        except Exception as e:
            latency = time.time() - start_time
            self.learner.track_metric("llm_latency", latency, {"status": "error", "error": str(e)})
            logger.error(f"Error in answer_query: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"An error occurred: {str(e)}"
            }

    def submit_quiz(
        self,
        user_id: str,
        node_id: str,
        question: str,
        expected_answer: str,
        user_answer: str,
        difficulty: str,
    ) -> dict:
        is_correct = self._score_answer(expected_answer, user_answer)
        updated = self.learner.record_quiz_result(
            user_id=user_id,
            node_id=node_id,
            question=question,
            expected_answer=expected_answer,
            user_answer=user_answer,
            is_correct=is_correct,
            difficulty=difficulty,
        )
        return {"is_correct": is_correct, "updated_mastery": updated}

    def learner_progress(self, user_id: str) -> dict:
        return self.learner.learner_progress(user_id=user_id)

    def health_snapshot(self) -> dict:
        return {
            "status": "ok",
            "data_dir": str(self.data_dir),
            "db_path": os.path.abspath(self.db_path),
            "nodes": self.knowledge_graph.graph.number_of_nodes(),
            "edges": self.knowledge_graph.graph.number_of_edges(),
        }

    def _collect_node_ids(self, retrieval_results: list[dict]) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        for item in retrieval_results:
            anchor_id = item.get("anchor_node_id")
            if anchor_id and anchor_id not in seen:
                seen.add(anchor_id)
                ids.append(anchor_id)
            for node in item.get("pedagogical_context", []):
                node_id = node.get("id")
                if node_id and node_id not in seen:
                    seen.add(node_id)
                    ids.append(node_id)
        return ids

    def _inject_attachment_context(
        self, retrieval_results: list[dict], attachments: list[dict]
    ) -> list[dict]:
        if not attachments:
            return retrieval_results
        extra_nodes = []
        for item in attachments:
            extra_nodes.append(
                {
                    "id": item.get("id", ""),
                    "heading": item.get("name", "Uploaded File"),
                    "content": item.get("text", ""),
                    "source": "upload",
                }
            )
        if not retrieval_results:
            return [
                {
                    "anchor_node_id": extra_nodes[0].get("id"),
                    "anchor_node": extra_nodes[0],
                    "score": 1.0,
                    "confidence": 1.0,
                    "pedagogical_context": extra_nodes[1:],
                }
            ]
        # Ensure at least the anchor node has high confidence if attachments are present
        retrieval_results[0]["confidence"] = 1.0
        retrieval_results[0]["pedagogical_context"] = (
            extra_nodes + retrieval_results[0].get("pedagogical_context", [])
        )
        return retrieval_results

    def _select_high_quality_context(
        self, retrieval_results: list[dict], requested_k: int
    ) -> list[dict]:
        if not retrieval_results:
            return []
        k = max(3, min(max(requested_k, 1), 5))
        ranked = sorted(
            retrieval_results,
            key=lambda item: (
                float(item.get("confidence", 0.0)),
                float(item.get("score", 0.0)),
            ),
            reverse=True,
        )
        selected: list[dict] = []
        seen = set()
        for item in ranked:
            anchor = item.get("anchor_node", {}) or {}
            heading = str(anchor.get("heading", "")).strip().lower()
            if heading and heading in seen:
                continue
            if heading:
                seen.add(heading)
            selected.append(item)
            if len(selected) >= k:
                break
        return selected

    def _score_answer(self, expected_answer: str, user_answer: str) -> bool:
        expected_tokens = self._tokens(expected_answer)
        user_tokens = self._tokens(user_answer)
        if not expected_tokens:
            return bool(user_tokens)
        if not user_tokens:
            return False

        overlap = len(set(expected_tokens).intersection(user_tokens))
        ratio = overlap / max(len(set(expected_tokens)), 1)
        return ratio >= 0.35

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]{3,}", text.lower())
