# SocratiQ Research Paper Folder

## Paper Outline + Figure List

### 1. Title (working)
SocratiQ: Vectorless Graph-Based Tutoring with Learner-Model Grounding

### 2. Abstract (4–6 sentences)
- Motivation: LLM-only tutoring lacks grounding and learner adaptation.
- Approach: Vectorless retrieval + knowledge graph + learner model + grounded Socratic teaching.
- Evaluation: precision@k, groundedness, hallucination rate, learning gain, latency with statistical reporting.
- Results: summarize baseline comparisons and key findings.
- Contribution: interpretable, evaluation-driven tutoring system.

### 3. Introduction
- Problem: pedagogically grounded tutoring with measurable learning outcomes.
- Gap: RAG/GraphRAG lack learner-model integration and learning-focused evaluation.
- Contributions summary.

### 4. Related Work
- LLM tutoring systems
- RAG and GraphRAG in education
- Learner modeling + spaced repetition
- Grounded generation evaluation

### 5. System Overview
- End-to-end pipeline diagram (Figure 1)
- Modular separation: core research vs product layers

### 6. Method
#### 6.1 Retrieval
- BM25 scoring
- graph traversal with bounded depth and edge weighting
- reranking + strict context filtering

#### 6.2 Knowledge Graph
- node construction
- edge types: prerequisite + related
- noise reduction constraints

#### 6.3 Learner Model
- mastery tracking
- BKT/spaced repetition updates
- adaptive difficulty and review scheduling

#### 6.4 Teaching Engine
- Socratic prompting
- quiz generation
- sentence-level grounding check

### 7. Evaluation
- Metrics: precision@k, recall@k, groundedness, hallucination rate, learning gain, latency
- Baselines: LLM-only, BM25-only, full system
- Multi-run eval + CI
- Human evaluation protocol

### 8. Results
- Table 1: baseline comparison
- Figure 2: learning gain trajectory
- Figure 3: groundedness vs hallucination

### 9. Discussion
- Strengths + weaknesses
- Where vectorless retrieval fails
- Impact of graph traversal + learner model

### 10. Limitations
- dataset scope
- evaluation proxy for learning gain
- human study requirements

### 11. Conclusion
- summary of contributions
- future work

---

## Figure List

1. Figure 1: Architecture Flow
   - Ingestion -> Graph -> Retrieval -> Learner Model -> Teaching Engine

2. Figure 2: Evaluation Pipeline
   - Baselines -> Metrics -> Statistical summaries

3. Figure 3: Learning Gain Over Time
   - Mastery improvement across sessions

4. Figure 4: Groundedness vs Hallucination
   - Trade-off scatter or bar chart by system mode

---

## Paper Artifacts

Recommended artifacts to include in paper/sections:
- abstract.md
- introduction.md
- method.md
- evaluation.md
- results.md
- discussion.md
- limitations.md
- conclusion.md

Recommended figures in paper/figures:
- architecture-flow.png
- evaluation-pipeline.png
- learning-gain.png
- groundedness-vs-hallucination.png
