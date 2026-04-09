---
wave: 2
depends_on: ["01-1-PLAN.md"]
files_modified: ["backend/app/core/graph_builder.py", "backend/app/core/__init__.py"]
autonomous: true
---

# Plan 2: Implement NetworkX Graph Builder

<task type="auto">
<name>Implement Graph Builder</name>
<files>backend/app/core/graph_builder.py</files>
<action>
Create `backend/app/core/graph_builder.py`.
Implement a `KnowledgeGraph` class utilizing `networkx`. 
Methods required:
1. `__init__`: Initializes `self.graph = nx.DiGraph()`
2. `build_from_chunks(chunks: list[dict])`: Takes the output from `MarkdownParser`. It should iterate the chunks, add nodes `self.graph.add_node(chunk['id'], **chunk)`.
It should track hierarchy: a level 2 chunk should have a directed edge `self.graph.add_edge(parent_id, chunk['id'])` pointing from its most recent level 1 ancestor.

*Note: You must import `networkx as nx`.*
</action>
<read_first>backend/app/core/graph_builder.py</read_first>
<acceptance_criteria>
- `backend/app/core/graph_builder.py` contains `class KnowledgeGraph:`
- `build_from_chunks` method exists.
</acceptance_criteria>
<verify>cat backend/app/core/graph_builder.py | grep build_from_chunks</verify>
<done>NetworkX hierarchy graph implementation completed</done>
</task>

<task type="auto">
<name>Implement spaCy entity extraction</name>
<files>backend/app/core/graph_builder.py</files>
<action>
Update `KnowledgeGraph.build_from_chunks` to run spaCy on each `chunk['content']`.
Initialize spaCy model `nlp = spacy.load("en_core_web_sm")`. Wait, actually provide a method `enrich_with_entities(nlp_model)` or do it locally. Just extract noun chunks `[chunk.text for chunk in doc.noun_chunks]` and add them to the node attributes as `entities`.
</action>
<read_first>backend/app/core/graph_builder.py</read_first>
<acceptance_criteria>
- The graph node insertion contains `entities` attributes extracted using spaCy.
</acceptance_criteria>
<verify>cat backend/app/core/graph_builder.py | grep spacy</verify>
<done>spaCy node enrichment completed</done>
</task>
