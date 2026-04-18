from __future__ import annotations

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.learning import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.schemas.files import FileAttachment, FileUploadResponse
from app.schemas.integrations import YouTubeSearchRequest, YouTubeSearchResponse
from app.schemas.quiz_generation import QuizGenerateRequest, QuizGenerateResponse
from app.schemas.quiz import (
    MCQGenerateRequest,
    MCQBatch,
    MCQQuestion,
    QuizSessionSubmit,
    QuizSessionResult,
    QuizHistory,
    QuizHistoryItem,
    LearnerProfile,
    LearnerUpdateRequest,
    TopicMastery,
)

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "ChatRequest",
    "ChatResponse",
    "IngestRequest",
    "QuizSubmitRequest",
    "QuizSubmitResponse",
    "FileAttachment",
    "FileUploadResponse",
    "YouTubeSearchRequest",
    "YouTubeSearchResponse",
    "QuizGenerateRequest",
    "QuizGenerateResponse",
    # New quiz + learner schemas
    "MCQGenerateRequest",
    "MCQBatch",
    "MCQQuestion",
    "QuizSessionSubmit",
    "QuizSessionResult",
    "QuizHistory",
    "QuizHistoryItem",
    "LearnerProfile",
    "LearnerUpdateRequest",
    "TopicMastery",
]
