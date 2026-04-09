---
wave: 1
depends_on: []
files_modified: ["backend/app/core/ingestion.py", "backend/requirements.txt"]
autonomous: true
---

# Plan 1: Implement Markdown DataLoader

<task type="auto">
<name>Setup python environment and dependencies</name>
<files>backend/requirements.txt</files>
<action>
Create `backend/requirements.txt` with the following content:
```text
fastapi>=0.103.1
uvicorn>=0.23.2
networkx>=3.1
spacy>=3.7.2
```
Create a lightweight `backend/app/core/__init__.py` to initialize the module.
</action>
<read_first>backend/requirements.txt</read_first>
<acceptance_criteria>
- `backend/requirements.txt` contains `networkx` and `spacy`.
</acceptance_criteria>
<verify>cat backend/requirements.txt | grep networkx</verify>
<done>Dependencies successfully logged in requirements.txt</done>
</task>

<task type="auto">
<name>Implement markdown parser logic</name>
<files>backend/app/core/ingestion.py</files>
<action>
Create `backend/app/core/ingestion.py`.
Implement a `MarkdownParser` class with a `parse_file(filepath: str) -> list[dict]` method.
It should read a markdown file and return a list of dictionaries.
Each dict represents a chunk:
- `id`: unique chunk ID (e.g., hash or slugized heading)
- `level`: Heading level (1 for '#', 2 for '##')
- `heading`: The text of the heading
- `content`: The text content under that heading
</action>
<read_first>backend/app/core/ingestion.py</read_first>
<acceptance_criteria>
- `backend/app/core/ingestion.py` contains `class MarkdownParser:`
- Contains `def parse_file(`
</acceptance_criteria>
<verify>cat backend/app/core/ingestion.py | grep MarkdownParser</verify>
<done>Parser implementation logic completed</done>
</task>
