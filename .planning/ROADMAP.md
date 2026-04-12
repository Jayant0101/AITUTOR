# Roadmap

## Phase 1: Ingestion & Seed Graph (Completed)
Implemented markdown ingestion (`MarkdownParser.parse_directory`), spaCy enrichment, and hierarchical NetworkX graph construction.

## Phase 2: Vectorless Retrieval Engine (Completed)
Implemented BM25 sparse retrieval with anchor-node selection and graph-based context expansion (ancestors + bounded descendants).

## Phase 3: Learner Model Integration (Completed)
Implemented SQLite learner schema (`users`, `nodes_mastery`, `quiz_history`) with mastery updates and spaced-review scheduling.

## Phase 4: LLM Teaching & Streamlit UI (Completed)
Implemented FastAPI orchestration and Streamlit UI, with Socratic/quiz teaching modes grounded on retrieved graph context.

## Phase 5: Authentication & Multi-Tenancy (Completed)
Added JWT-based authentication (register, login, token verification), bcrypt password hashing, CORS middleware, and protected all learning endpoints with user context extraction.

## Phase 6: React Frontend Transition (Completed)
Replaced Streamlit prototype with a React + Vite application featuring glassmorphism dark theme, animated UI, sidebar navigation, auth pages (Login/Register), Dashboard, Socratic Chat, and Progress tracking.

## Phase 7: Advanced Adaptive Learning & BKT (Planned)
Upgrade the spaced repetition learner model to use Bayesian Knowledge Tracing (BKT) for more rigorous cognitive state modeling.

## Phase 8: Hardening & Cloud Deployment (Planned)
Finalize production Docker setup with Nginx reverse proxy, build optimizations, and deployment-ready configuration.
