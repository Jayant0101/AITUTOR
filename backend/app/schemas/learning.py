from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    data_dir: str | None = None


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)
    mode: Literal["socratic", "quiz"] = "socratic"
    attachments: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    # Status is always present: "success" | "no_data"
    status: str = "success"
    # Present only for no_data responses
    message: Optional[str] = None
    action: Optional[str] = None
    # Present only for success responses
    query: Optional[str] = None
    mode: Optional[str] = None
    result: Optional[dict] = None
    retrieval: Optional[list[dict]] = None
    # Sources list for convenience (mirrors citations from result)
    sources: Optional[list[Any]] = None
    # Quality signals
    confidence: Optional[float] = None
    source_type: Optional[str] = None       # "local" | "web" | "hybrid"
    follow_up_question: Optional[str] = None


class QuizSubmitRequest(BaseModel):
    node_id: str
    question: str
    expected_answer: str
    user_answer: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizSubmitResponse(BaseModel):
    is_correct: bool
    updated_mastery: dict
