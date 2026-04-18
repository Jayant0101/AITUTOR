from __future__ import annotations

"""
Ranking facade package.

Current implementation keeps MMR/diversity selection inside `app.retrieval.retrieval`
to avoid risky large-scale refactors. This package exists to match the intended
folder architecture and provide a stable import surface for future extraction.
"""

__all__: list[str] = []

