from __future__ import annotations

from app.api.routes.chat import router as chat_router
from app.api.routes.quiz import router as quiz_router
from app.api.routes.learner import router as learner_router
from app.api.routes.ingestion import router as ingestion_router

__all__ = ["chat_router", "quiz_router", "learner_router", "ingestion_router"]
