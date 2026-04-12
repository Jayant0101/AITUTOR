# Vectorless Graph-Based AI Learning Assistant

This repository now implements the Phase 1-4 roadmap end-to-end:

- Phase 1: Markdown ingestion and seeded concept graph
- Phase 2: BM25 sparse retrieval with graph context expansion
- Phase 3: SQLite learner model with mastery tracking and spaced review scheduling
- Phase 4: FastAPI teaching API + Streamlit UI for Socratic chat and quiz workflows

## Project Structure

- `backend/app/core`: ingestion, graph builder, retrieval engine
- `backend/app/services`: learner tracker, teaching agent, orchestration service
- `backend/app/main.py`: FastAPI entrypoint
- `backend/data`: markdown knowledge source files
- `frontend/streamlit_app.py`: Streamlit interface

## Run Locally

Backend:

```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

Frontend:

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/streamlit_app.py
```

Default URLs:

- API: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

## Docker

```bash
docker compose up --build
```

## Production run

```bash
docker compose -f docker-compose.prod.yml up --build
```

Default URL:

- UI + API proxy: `http://localhost` (API served under `/api`)

## API Endpoints

- `GET /health`
- `POST /ingest`
- `POST /chat` (`mode`: `socratic` or `quiz`)
- `POST /quiz/submit`
- `GET /learner/{user_id}/progress`
