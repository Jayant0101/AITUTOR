# Roadmap

Phase 1 plans the core infrastructure. Phase 2 extends logic. Phase 3 assembles the components.

## Phase 1: Ingestion & Seed Graph
Implement `DataLoader` for Markdown. Implement spaCy keyword extraction. Build initial NetworkX graph based strictly on section hierarchy.

## Phase 2: Vectorless Retrieval Engine
Implement `rank_bm25` indexer. Tie `RetrievalEngine` to NetworkX to perform the BM25 -> Anchor Node -> Graph Expansion pipeline.

## Phase 3: Learner Model Integration
Scaffold SQLite schemas. Implement mastery update logic based on dummy quiz submissions. Dockerize the setup.

## Phase 4: LLM Teaching & Streamlit UI
Write constrained Gemini prompts. Bind the complete pipeline to a Streamlit interactive chat and quiz interface.
