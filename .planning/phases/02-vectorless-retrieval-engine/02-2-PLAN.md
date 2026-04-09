---
wave: 2
depends_on: ["02-1-PLAN.md"]
files_modified: ["backend/app/core/retrieval.py"]
autonomous: true
---

# Plan 2: Implement Graph Expansion

<task type="auto">
<name>Expand Retrieval Subgraph</name>
<files>backend/app/core/retrieval.py</files>
<action>
Update `RetrievalEngine.search` to also return the expanded pedagogical context.
Add method `_expand_context(self, anchor_node_id: str) -> list[dict]`:
1. Use `nx.ancestors` or path to root to get the parent nodes.
2. Use `nx.descendants` (depth=1) or `list(self.kg.graph.successors(node))` to capture immediate children of the anchor node.
3. Return the grouped text contents of the ancestor hierarchy + anchor + immediate children.
Update `search()` to return this expanded chunk list instead of just the anchor node.
</action>
<read_first>backend/app/core/retrieval.py</read_first>
<acceptance_criteria>
- File contains `_expand_context`.
- `search()` method utilizes the logic.
</acceptance_criteria>
<verify>cat backend/app/core/retrieval.py | grep _expand_context</verify>
<done>Graph expansion logic implemented</done>
</task>
