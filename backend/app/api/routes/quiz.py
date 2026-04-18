"""
Quiz routes
===========
  POST /quiz/generate   — generate MCQ batch
  POST /quiz/submit     — grade + record quiz session
  GET  /quiz/history    — past quiz sessions for current user
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from app.schemas import (
    MCQGenerateRequest,
    MCQBatch,
    QuizSessionSubmit,
    QuizSessionResult,
    QuizHistory,
    QuizHistoryItem,
)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


def _get_service():
    from app.main import service
    return service


def _get_quiz_engine():
    from app.main import quiz_engine
    return quiz_engine


@router.post("/generate", response_model=MCQBatch, summary="Generate an MCQ quiz batch")
def generate_mcq(
    request: MCQGenerateRequest,
    current: dict = Depends(get_current_user),
) -> MCQBatch:
    """
    Generate a quiz on a topic with the requested difficulty and number of questions.

    Uses the LLM (Gemini/OpenAI) when an API key is configured; otherwise
    falls back to a template generator from the knowledge graph.
    """
    try:
        svc = _get_service()
        engine = _get_quiz_engine()
        batch = engine.generate(
            topic=request.topic,
            difficulty=request.difficulty,
            num_questions=request.num_questions,
        )
        # Phase 1: Track quiz start
        svc.learner.track_event(
            user_id=current["user_id"],
            event_type="quiz_start",
            metadata={"topic": request.topic, "difficulty": request.difficulty, "num_questions": request.num_questions}
        )
        return MCQBatch(**batch)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Quiz generation failed")
        raise HTTPException(status_code=500, detail="Failed to generate quiz")


@router.post("/submit", response_model=QuizSessionResult, summary="Submit quiz answers and get score")
def submit_quiz(
    request: QuizSessionSubmit,
    current: dict = Depends(get_current_user),
) -> QuizSessionResult:
    """
    Grade a quiz, record the session in the DB, and update the learner profile.

    Returns score, percentage, time_taken, and adaptive feedback.
    """
    try:
        engine = _get_quiz_engine()
        svc = _get_service()

        result = engine.grade(
            quiz_id=request.quiz_id,
            user_answers=request.answers,
            time_taken=request.time_taken,
        )

        # Persist the session and update learner_profile
        svc.learner.record_quiz_session(
            user_id=current["user_id"],
            topic=result["topic"],
            difficulty=result["difficulty"],
            score=result["score"],
            total=result["total"],
            time_taken=result["time_taken"],
            feedback=result["feedback"],
        )

        # Phase 1: Track quiz submit
        svc.learner.track_event(
            user_id=current["user_id"],
            event_type="quiz_submit",
            metadata={
                "quiz_id": request.quiz_id,
                "topic": result["topic"],
                "score": result["score"],
                "total": result["total"],
                "percentage": result["percentage"]
            }
        )

        return QuizSessionResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Quiz submission failed")
        raise HTTPException(status_code=500, detail="Failed to submit quiz")


@router.get("/history", response_model=QuizHistory, summary="Get quiz history for current user")
def quiz_history(
    limit: int = 20,
    current: dict = Depends(get_current_user),
) -> QuizHistory:
    try:
        svc = _get_service()
        sessions_raw = svc.learner.get_quiz_history(user_id=current["user_id"], limit=limit)
        sessions = [
            QuizHistoryItem(
                quiz_id=str(s["id"]),
                topic=s["topic"],
                difficulty=s["difficulty"],
                score=s["score"],
                total=s["total"],
                percentage=s["percentage"],
                time_taken=s["time_taken"],
                taken_at=s["taken_at"],
            )
            for s in sessions_raw
        ]
        return QuizHistory(sessions=sessions, total_sessions=len(sessions))
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Quiz history retrieval failed")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")
