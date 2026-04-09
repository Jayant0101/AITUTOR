# Phase 2 Research: Vectorless Retrieval Engine

## Objective
Implement `rank_bm25` search over the knowledge graph nodes previously seeded by Phase 1, followed by a Graph Expansion logic that returns a subgraph representing pedagogical context.

## Technical Context
- **BM25 Search**: `rank_bm25` requires tokenized string arrays. The search corpus will be the textual contents of the chunked documents, along with their associated spaCy entities.
- **Graph Expansion**: Once an anchor node is retrieved via BM25, we use `networkx` to expand to a configurable degree:
  - Add its ancestors (path from root to node).
  - Add its immediate children (level + 1).

## Required Libraries
- `rank_bm25` (Must be added to `backend/requirements.txt`).

## Validation Architecture
- Verify that `RetrievalEngine` returns a subset graph containing the BM25 result and its parent node.
