"""
Learner profile routes
======================
  GET  /learner/profile  — full per-topic mastery profile
  POST /learner/update   — manually update a topic mastery score
  GET  /learner/progress — existing legacy progress endpoint (node-level)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.schemas import LearnerProfile, LearnerUpdateRequest, TopicMastery

router = APIRouter(prefix="/learner", tags=["Learner"])


def _get_service():
    from app.main import service
    return service


@router.get("/profile", response_model=LearnerProfile, summary="Get learner topic-mastery profile")
def learner_profile(current: dict = Depends(get_current_user)) -> LearnerProfile:
    """
    Returns per-topic mastery scores, quiz counts, and overall mastery.

    Example response:
    {
      "user_id": "...",
      "topics": [
        {"topic": "BM25", "mastery_score": 72.5, "quizzes_taken": 3, "avg_score": 70.0}
      ],
      "overall_mastery": 72.5,
      "total_quizzes": 3
    }
    """
    try:
        svc = _get_service()
        raw = svc.learner.get_learner_profile(user_id=current["user_id"])
        topics = [
            TopicMastery(
                topic=t["topic"],
                mastery_score=t["mastery_score"],
                quizzes_taken=t["quizzes_taken"],
                avg_score=t["avg_score"],
                last_updated=t.get("last_updated"),
            )
            for t in raw["topics"]
        ]
        return LearnerProfile(
            user_id=raw["user_id"],
            topics=topics,
            overall_mastery=raw["overall_mastery"],
            total_quizzes=raw["total_quizzes"],
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Learner profile retrieval failed")
        raise HTTPException(status_code=500, detail="Failed to retrieve learner profile")


@router.post("/update", summary="Manually update topic mastery score")
def update_mastery(
    body: LearnerUpdateRequest,
    current: dict = Depends(get_current_user),
) -> dict:
    """
    Manually set a mastery score for a topic (0-100).
    Useful for admin overrides or initial calibration.
    """
    try:
        svc = _get_service()
        return svc.learner.update_topic_mastery(
            user_id=current["user_id"],
            topic=body.topic,
            mastery_score=body.mastery_score,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Mastery update failed")
        raise HTTPException(status_code=500, detail="Failed to update mastery")


@router.get("/progress", summary="Node-level learning progress (legacy)")
def node_progress(current: dict = Depends(get_current_user)) -> dict:
    """Legacy endpoint — returns node-level BKT mastery from the retrieval graph."""
    try:
        svc = _get_service()
        return svc.learner.learner_progress(user_id=current["user_id"])
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Progress retrieval failed")
        raise HTTPException(status_code=500, detail="Failed to retrieve progress")

