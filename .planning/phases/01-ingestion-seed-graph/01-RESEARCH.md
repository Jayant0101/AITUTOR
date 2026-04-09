# Phase 1 Research: Ingestion & Seed Graph

## Objective
Determine the implementation approach for Phase 1: Ingestion & Seed Graph (Markdown DataLoader, spaCy keyword extraction, NetworkX structure).

## Technical Context
- **DataLoader**: Needs to parse markdown documents located in `data/`, grouping chunked content by headings (`#`, `##`, etc.). We will use Python's built-in `re` module or `markdown` library to identify headings and their associated bodies.
- **spaCy Integration**: We will install the `en_core_web_sm` model to extract noun chunks and named entities. These entities are the potential mapping keywords for our document chunks.
- **NetworkX Graph**: Each markdown heading becomes a structural node. Sections are represented as nodes, with hierarchical edges connecting them (e.g. `## Section 1.1` is a child of `# Section 1`). Extracted keywords/entities will map to the nodes they belong to.

## Required Libraries
- `networkx`
- `spacy`
- `python-markdown` or basic `regex` logic. (We'll use standard `re` for simplicity in parsing structural chunks, reducing dependency overhead, or `markdown-it-py`). Let's stick to `re` to minimize bloat since it's just header splitting.

## Potential Pitfalls
- Handling huge markdown files requiring memory limits. (Not a concern here, assuming reasonable sizes).
- spaCy missing dependencies. (`python -m spacy download en_core_web_sm` MUST be run).

## Validation Architecture
- **Verification**: Run a mock ingest script on a test `markdown` file and verify Graph nodes and edges are properly created via NetworkX's `G.nodes()` and `G.edges()`.
