from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.evaluation.build_cases import build_cases
from app.evaluation.run_all import EvalCase, aggregate, build_retrieval, run_case
from app.llm.assistant_service import LearningAssistantService
from app.main import app


class CheckResult:
    def __init__(self, name: str, ok: bool, detail: str) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail


def _print_result(result: CheckResult) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"[{status}] {result.name}: {result.detail}")


def _register_and_auth(client: TestClient) -> str:
    email = f"qa-{uuid.uuid4().hex[:8]}@example.com"
    password = "qa-password-123"
    reg = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "QA User"},
    )
    reg.raise_for_status()
    token = reg.json()["access_token"]
    return token


def run_system_validation() -> dict:
    results: list[CheckResult] = []
    artifacts: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="socratiq-qa-") as tmp:
        tmp_path = Path(tmp)
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "learner.db"

        sample = data_dir / "sample.md"
        sample.write_text(
            "\n".join(
                [
                    "# Retrieval Foundations",
                    "BM25 scores lexical relevance in chunks.",
                    "## Graph Expansion",
                    "Graph traversal adds prerequisite context to the anchor node.",
                    "## Reranking",
                    "Reranker prioritizes query overlap and lexical relevance.",
                    "## Socratic Teaching",
                    "Socratic tutoring guides via questions and grounded evidence.",
                ]
            ),
            encoding="utf-8",
        )

        # Part 1: module-level validation
        service = LearningAssistantService(data_dir=str(data_dir), db_path=str(db_path))
        service.initialize()
        ingest_stats = service.load_knowledge_base(str(data_dir))
        results.append(
            CheckResult(
                "ingestion_and_graph",
                ingest_stats["nodes"] > 0 and ingest_stats["edges"] > 0,
                f"chunks={ingest_stats['chunks_loaded']} nodes={ingest_stats['nodes']} edges={ingest_stats['edges']}",
            )
        )

        retrieval = service.retrieval
        retrieval_items = retrieval.search("How does graph expansion help BM25?", top_n=3, expand_depth=1) if retrieval else []
        rerank_changed = False
        if retrieval and retrieval_items:
            query_text = "graph expansion bm25"
            base_tokens = retrieval._tokenize(query_text)
            expanded = retrieval._expand_query(base_tokens)
            scores = retrieval.bm25.get_scores(expanded) if retrieval.bm25 else []
            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:6]
            reranked = retrieval._rerank_candidates(
                candidate_indices=ranked,
                bm25_scores=scores,
                query_tokens=base_tokens,
                query_phrases=retrieval._extract_query_phrases(query_text),
                query_entities=retrieval._extract_query_entities(query_text),
                query_intent=retrieval._detect_query_intent(query_text),
            )
            rerank_changed = ranked != reranked

        results.append(
            CheckResult(
                "retrieval_bm25_graph_rerank",
                bool(retrieval_items),
                f"top_results={len(retrieval_items)} rerank_reordered={rerank_changed}",
            )
        )

        mastery_stub = service.learner.get_mastery_by_node("qa-user", [r["anchor_node_id"] for r in retrieval_items if r.get("anchor_node_id")])
        socratic = service.teacher.generate(
            query="Explain graph expansion step by step.",
            retrieval_results=retrieval_items,
            mastery_by_node=mastery_stub,
            mode="socratic",
        )
        has_structure = bool(socratic.get("text", "").strip()) and ("?" in socratic.get("text", "") or socratic.get("follow_up_question"))
        results.append(
            CheckResult(
                "teaching_agent_output",
                has_structure and bool(socratic.get("citations")),
                f"text_len={len(socratic.get('text', ''))} citations={len(socratic.get('citations', []))}",
            )
        )
        

        quiz = service.teacher.generate(
            query="Quiz me on reranking.",
            retrieval_results=retrieval_items,
            mastery_by_node=mastery_stub,
            mode="quiz",
        )
        results.append(
            CheckResult(
                "quiz_generation",
                bool(quiz.get("question")) and bool(quiz.get("expected_answer")),
                f"difficulty={quiz.get('difficulty', 'n/a')}",
            )
        )

        if retrieval_items:
            focus_id = retrieval_items[0]["anchor_node_id"]
            wrong = service.submit_quiz(
                user_id="qa-user",
                node_id=focus_id,
                question=quiz.get("question", "q"),
                expected_answer=quiz.get("expected_answer", "a"),
                user_answer="incorrect answer",
                difficulty="medium",
            )
            right = service.submit_quiz(
                user_id="qa-user",
                node_id=focus_id,
                question=quiz.get("question", "q"),
                expected_answer=quiz.get("expected_answer", "a"),
                user_answer=quiz.get("expected_answer", ""),
                difficulty="medium",
            )
            progress = service.learner_progress("qa-user")
            learner_ok = (
                right["updated_mastery"]["attempts"] >= 2
                and progress["tracked_nodes"] >= 1
                and isinstance(progress["weak_nodes"], list)
            )
            results.append(
                CheckResult(
                    "learner_model_updates",
                    learner_ok,
                    f"attempts={right['updated_mastery']['attempts']} tracked_nodes={progress['tracked_nodes']}",
                )
            )
        else:
            results.append(CheckResult("learner_model_updates", False, "No retrieval result to anchor learner updates"))

        # Part 2 + Part 4: API pipeline + edge handling
        client = TestClient(app)
        token = _register_and_auth(client)
        headers = {"Authorization": f"Bearer {token}"}

        health = client.get("/health")
        ingest = client.post("/ingest", json={}, headers=headers)
        chat = client.post(
            "/chat",
            json={"query": "What is BM25?", "mode": "socratic", "top_k": 3},
            headers=headers,
        )
        quiz_chat = client.post(
            "/chat",
            json={"query": "Quiz me on BM25", "mode": "quiz", "top_k": 3},
            headers=headers,
        )
        # FastAPI TestClient may return httpx Response; do not rely on `.ok`.
        quiz_payload = (
            quiz_chat.json().get("result", {})
            if getattr(quiz_chat, "ok", False) or quiz_chat.status_code < 400
            else {}
        )
        submit = client.post(
            "/quiz/submit",
            json={
                "node_id": quiz_payload.get("focus_node_id", "unknown"),
                "question": quiz_payload.get("question", "What is BM25?"),
                "expected_answer": quiz_payload.get("expected_answer", "lexical retrieval"),
                "user_answer": quiz_payload.get("expected_answer", "lexical retrieval"),
                "difficulty": quiz_payload.get("difficulty", "medium"),
            },
            headers=headers,
        )
        progress_api = client.get("/learner/progress", headers=headers)
        pipeline_ok = all(
            [
                health.status_code == 200,
                ingest.status_code == 200,
                chat.status_code == 200,
                quiz_chat.status_code == 200,
                submit.status_code == 200,
                progress_api.status_code == 200,
            ]
        )
        results.append(
            CheckResult(
                "full_pipeline_api_flow",
                pipeline_ok,
                f"statuses={[health.status_code, ingest.status_code, chat.status_code, quiz_chat.status_code, submit.status_code, progress_api.status_code]}",
            )
        )

        empty_query = client.post("/chat", json={"query": "   ", "mode": "socratic"}, headers=headers)
        unknown_topic = client.post("/chat", json={"query": "zzzz_nonexistent_topic_123", "mode": "socratic"}, headers=headers)
        missing_data = client.post("/quiz/generate", json={"file_ids": []}, headers=headers)
        edge_ok = (
            empty_query.status_code == 400
            and unknown_topic.status_code in (200, 404)
            and missing_data.status_code == 400
        )
        results.append(
            CheckResult(
                "error_handling_edge_cases",
                edge_ok,
                f"empty_query={empty_query.status_code} unknown_topic={unknown_topic.status_code} missing_data={missing_data.status_code}",
            )
        )

        # LLM fallback check with invalid provider settings
        old_provider = os.environ.get("LLM_PROVIDER")
        old_model = os.environ.get("LLM_MODEL")
        try:
            os.environ["LLM_PROVIDER"] = "openai"
            os.environ["LLM_MODEL"] = "gpt-4o-mini"
            fallback_service = LearningAssistantService(data_dir=str(data_dir), db_path=str(tmp_path / "fallback.db"))
            fallback_service.initialize()
            fallback = fallback_service.answer_query(
                user_id="fallback-user",
                query="Explain reranking",
                top_k=2,
                mode="socratic",
            )
            fallback_ok = bool(fallback.get("result", {}).get("text", ""))
            results.append(
                CheckResult(
                    "llm_failure_fallback",
                    fallback_ok,
                    f"text_len={len(fallback.get('result', {}).get('text', ''))}",
                )
            )
        finally:
            if old_provider is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = old_provider
            if old_model is None:
                os.environ.pop("LLM_MODEL", None)
            else:
                os.environ["LLM_MODEL"] = old_model

        # Part 1(6): evaluation metrics and JSON artifact
        cases = build_cases(str(data_dir), max_cases=5)
        eval_cases = [
            EvalCase(
                query=c["query"],
                gold_node_ids=set(c["gold_node_ids"]),
                relevance_by_id={
                    str(node_id): float(score)
                    for node_id, score in (c.get("relevance_by_id") or {}).items()
                },
                hard_negative_node_ids=set(c.get("hard_negative_node_ids") or []),
            )
            for c in cases
        ]
        eval_retrieval = build_retrieval(str(data_dir))
        eval_metrics = [
            run_case(case, eval_retrieval, service.teacher, top_k=3, expand_depth=1, mode="full_system")
            for case in eval_cases
        ]
        summary = aggregate(eval_metrics)
        eval_ok = "precision@k" in summary and "groundedness" in summary and "learning_gain" in summary
        results.append(
            CheckResult(
                "evaluation_metrics",
                eval_ok,
                f"metrics={list(summary.keys())}",
            )
        )

        out = tmp_path / "summary_validation.json"
        out.write_text(json.dumps({"summary": summary}, indent=2), encoding="utf-8")
        artifacts["evaluation_json"] = str(out)
        results.append(
            CheckResult(
                "evaluation_json_generated",
                out.exists() and out.stat().st_size > 0,
                str(out),
            )
        )

    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    for item in results:
        _print_result(item)
    print(f"\nTotal: {len(results)} | Passed: {len(passed)} | Failed: {len(failed)}")

    return {
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "results": [{"name": r.name, "ok": r.ok, "detail": r.detail} for r in results],
        "artifacts": artifacts,
    }


if __name__ == "__main__":
    report = run_system_validation()
    if report["failed"] > 0:
        raise SystemExit(1)
