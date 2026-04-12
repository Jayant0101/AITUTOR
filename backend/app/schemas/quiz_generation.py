from __future__ import annotations

from pydantic import BaseModel, Field


class QuizGenerateRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)


class QuizGenerateResponse(BaseModel):
    question: str
    expected_answer: str
    difficulty: str = "medium"
    citations: list[dict] = Field(default_factory=list)
