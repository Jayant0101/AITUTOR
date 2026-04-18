"""
Chat routes — /chat/query and /chat/stream
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.auth import get_current_user
from app.schemas import ChatRequest, ChatResponse, QuizSubmitRequest

router = APIRouter(prefix="/chat", tags=["Chat"])


def _get_service():
    """Lazy import to avoid circular deps; main.py sets this at startup."""
    from app.main import service
    return service


@router.post("/query", response_model=ChatResponse, summary="Ask a question (alias: /chat)")
@router.post("", response_model=ChatResponse, include_in_schema=False)
def chat_query(
    request: ChatRequest,
    current: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Hybrid retrieval → LLM explanation → grounded response.

    Returns:
    - status="success"  + answer, sources, confidence, source_type
    - status="no_data"  + message + action="upload_required"
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    try:
        svc = _get_service()

        from app.main import _hydrate_attachments
        payload = svc.answer_query(
            user_id=current["user_id"],
            query=request.query,
            top_k=request.top_k,
            mode=request.mode,
            attachments=_hydrate_attachments(request.attachments),
        )

        # Phase 1: Track chat query
        svc.learner.track_event(
            user_id=current["user_id"],
            event_type="chat_query",
            metadata={"query": request.query, "mode": request.mode, "status": payload.get("status")}
        )

        if payload.get("status") == "no_data":
            return ChatResponse(
                status="no_data",
                message=payload["message"],
                action=payload["action"],
            )
        
        if payload.get("status") == "error":
             raise HTTPException(status_code=500, detail=payload.get("message", "LLM generation failed"))

        return ChatResponse(**payload)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Chat query failed")
        raise HTTPException(status_code=500, detail="Something went wrong")


@router.post("/stream", summary="Streaming chat response")
def chat_stream(
    request: ChatRequest,
    current: dict = Depends(get_current_user),
) -> StreamingResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    try:
        svc = _get_service()
        from app.main import _hydrate_attachments
        payload = svc.answer_query(
            user_id=current["user_id"],
            query=request.query,
            top_k=request.top_k,
            mode=request.mode,
            attachments=_hydrate_attachments(request.attachments),
        )

        if payload.get("status") == "no_data":
            text = payload.get("message", "No relevant documents found.")
        elif payload.get("status") == "error":
            text = f"Error: {payload.get('message', 'LLM failed')}"
        else:
            text = payload.get("result", {}).get("text", "")

        def event_stream():
            for token in text.split(" "):
                yield token + " "

        return StreamingResponse(event_stream(), media_type="text/plain")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Chat stream failed")
        raise HTTPException(status_code=500, detail="Streaming failed")
    
@router.post("/quiz/submit", response_model=dict, summary="Submit a socratic chat quiz answer")
def submit_chat_quiz(
    request: QuizSubmitRequest,
    current: dict = Depends(get_current_user),
) -> dict:
    try:
        svc = _get_service()
        return svc.submit_quiz(
            user_id=current["user_id"],
            node_id=request.node_id,
            question=request.question,
            expected_answer=request.expected_answer,
            user_answer=request.user_answer,
            difficulty=request.difficulty,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Quiz submission failed")
        raise HTTPException(status_code=500, detail="Submission failed")
