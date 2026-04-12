from __future__ import annotations

import os
import re
from pathlib import Path

from app.graph.graph_builder import KnowledgeGraph
from app.ingestion.ingestion import MarkdownParser
from app.retrieval.retrieval import RetrievalEngine
from app.learner.learner_tracker import LearnerTracker
from app.teaching.teaching_agent import TeachingAgent


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
        self.data_dir.mkdir(parents=True, exist_ok=True)
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

    def answer_query(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        mode: str = "socratic",
        attachments: list[dict] | None = None,
    ) -> dict:
        self.learner.ensure_user(user_id)
        retrieval_results = (
            self.retrieval.search(query=query, top_n=max(top_k, 1), expand_depth=1)
            if self.retrieval
            else []
        )

        if attachments:
            retrieval_results = self._inject_attachment_context(
                retrieval_results=retrieval_results, attachments=attachments
            )

        node_ids = self._collect_node_ids(retrieval_results)
        mastery_by_node = self.learner.get_mastery_by_node(user_id=user_id, node_ids=node_ids)
        teaching_payload = self.teacher.generate(
            query=query,
            retrieval_results=retrieval_results,
            mastery_by_node=mastery_by_node,
            mode=mode,
        )

        return {
            "query": query,
            "mode": mode,
            "result": teaching_payload,
            "retrieval": retrieval_results,
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
                    "score": 0.0,
                    "pedagogical_context": extra_nodes[1:],
                }
            ]
        retrieval_results[0]["pedagogical_context"] = (
            extra_nodes + retrieval_results[0].get("pedagogical_context", [])
        )
        return retrieval_results

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
