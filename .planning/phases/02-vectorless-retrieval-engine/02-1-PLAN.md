---
wave: 1
depends_on: []
files_modified: ["backend/app/core/retrieval.py", "backend/requirements.txt", "backend/app/core/graph_builder.py"]
autonomous: true
---

# Plan 1: Implement BM25 Indexer

<task type="auto">
<name>Add rank_bm25 to requirements</name>
<files>backend/requirements.txt</files>
<action>
Append `rank_bm25>=0.2.2` to `backend/requirements.txt`.
</action>
<read_first>backend/requirements.txt</read_first>
<acceptance_criteria>
- `backend/requirements.txt` contains `rank_bm25`.
</acceptance_criteria>
<verify>cat backend/requirements.txt | grep rank_bm25</verify>
<done>Requirement appended</done>
</task>

<task type="auto">
<name>Implement RetrievalEngine</name>
<files>backend/app/core/retrieval.py</files>
<action>
Create `backend/app/core/retrieval.py`.
Implement a `RetrievalEngine` class.
- `__init__(self, knowledge_graph: KnowledgeGraph)`: takes the KnowledgeGraph instance.
- `_build_index(self)`: Iterates over `self.kg.graph.nodes(data=True)` and creates a BM25 index over the chunk contents plus entities. Store node IDs aligned with the BM25 array index.
- `search(self, query: str, top_n: int = 1) -> dict`: Tokenizes query, calls `BM25Okapi.get_top_n`, and returns the best matching context nodes.
</action>
<read_first>backend/app/core/retrieval.py</read_first>
<acceptance_criteria>
- File creates the logic required for rank_bm25 processing over the NetworkX nodes.
</acceptance_criteria>
<verify>cat backend/app/core/retrieval.py | grep RetrievalEngine</verify>
<done>Retrieval Engine Implemented</done>
</task>
