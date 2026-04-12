"""Compatibility shims for legacy imports."""

from app.graph.graph_builder import KnowledgeGraph
from app.ingestion.ingestion import MarkdownParser
from app.retrieval.retrieval import RetrievalEngine

__all__ = ["MarkdownParser", "KnowledgeGraph", "RetrievalEngine"]
