"""
Ingestion routes
================
  POST /ingest          — reload knowledge base from data dir
  POST /ingest/upload   — upload MD/PDF/image file (alias: /files/upload)
  POST /files/upload    — legacy alias
  POST /search/youtube  — YouTube search integration
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.auth import get_current_user
from app.schemas import (
    FileUploadResponse,
    IngestRequest,
    YouTubeSearchRequest,
    YouTubeSearchResponse,
)

router = APIRouter(tags=["Ingestion"])


def _get_service():
    from app.main import service
    return service


def _get_file_store():
    from app.main import file_store
    return file_store


def _get_file_parser():
    from app.main import file_parser
    return file_parser


def _get_youtube():
    from app.main import youtube_client
    return youtube_client


def _get_uploads_dir() -> Path:
    from app.main import uploads_dir
    return uploads_dir


@router.post("/ingest", summary="Reload knowledge base from data directory")
def ingest(
    request: IngestRequest,
    current: dict = Depends(get_current_user),
) -> dict:
    try:
        result = _get_service().load_knowledge_base(data_dir=request.data_dir)
        return {"status": "ok", **result}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ingestion failed")
        raise HTTPException(status_code=500, detail="Failed to reload knowledge base")


@router.post(
    "/ingest/upload",
    response_model=FileUploadResponse,
    summary="Upload a document (MD, PDF, image)",
)
@router.post("/files/upload", response_model=FileUploadResponse, include_in_schema=False)
def upload_file(
    file: UploadFile = File(...),
    current: dict = Depends(get_current_user),
) -> FileUploadResponse:
    """
    Upload a document. Supported types: .md, .pdf, images.
    The file is stored on disk and its metadata recorded in the DB.
    Use the returned 'id' in /chat/query attachments to ground answers.
    """
    # Phase 3 Security Check: File type/size validation
    allowed_suffixes = {".pdf", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    suffix = Path(file.filename).suffix.lower() if file.filename else ""
    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(allowed_suffixes)}"
        )

    try:
        uploads_dir = _get_uploads_dir()
        file_store = _get_file_store()

        file_id = str(uuid.uuid4())
        target_path = uploads_dir / f"{file_id}{suffix}"

        # Read content in chunks to handle large files (Scenario 3)
        size = 0
        with target_path.open("wb") as handle:
            while chunk := file.file.read(1024 * 1024):  # 1MB chunks
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    handle.close()
                    target_path.unlink()  # delete partial file
                    raise HTTPException(status_code=413, detail="File too large (max 50MB)")
                handle.write(chunk)

        file_store.add_file(
            file_id=file_id,
            name=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            size=size,
            path=str(target_path),
        )
        # Phase 1: Track document upload
        svc = _get_service()
        svc.learner.track_event(
            user_id=current["user_id"],
            event_type="document_upload",
            metadata={"file_id": file_id, "name": file.filename, "size": size}
        )

        return FileUploadResponse(
            id=file_id,
            name=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            size=size,
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("File upload failed")
        raise HTTPException(status_code=500, detail="File upload failed")


@router.post(
    "/search/youtube",
    response_model=YouTubeSearchResponse,
    summary="Search YouTube for educational videos",
)
def search_youtube(
    request: YouTubeSearchRequest,
    current: dict = Depends(get_current_user),
) -> YouTubeSearchResponse:
    try:
        yt = _get_youtube()
        results = yt.search(request.query, max_results=1)
        if not results:
            raise HTTPException(status_code=404, detail="No YouTube results")
        top = results[0]
        return YouTubeSearchResponse(
            title=top.get("title", ""),
            url=top.get("url", ""),
            channel=top.get("channel", ""),
            snippet=top.get("snippet", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("YouTube search failed")
        raise HTTPException(status_code=500, detail="YouTube search failed")
