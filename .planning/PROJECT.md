# AI Learning Assistant

## What This Is
We are building a production-grade, AI-powered personalized learning assistant.

## The Pitch
An adaptive cognitive learning system using Python, FastAPI, and Streamlit. It uses a vectorless graph-based retrieval approach using rank_bm25 and NetworkX, combined with a SQLite learner model that dictates Gemini's teaching focus.

## Target Audience
Learners requiring structured, syllabus-based pedagogical guidance.

## Core Value
Grounded Socratic teaching that reduces AI hallucination by enforcing structured graph traversal and incorporating a stateful mastery tracker.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI | High performance, Python ecosystem (NetworkX, spaCy). | Completed |
| NetworkX | In-memory graph engine, avoids Neo4j overhead. | Completed |
| rank_bm25 | Gold standard for sparse retrieval, avoids dense embeddings. | Completed |
| SQLite | Lightweight persistence for mastery tracking and progress. | Completed |
| Streamlit | Rapid prototyping for the AI chat and dashboard UI. | Completed |
