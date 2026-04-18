from __future__ import annotations

import json
import os
import re
from typing import Any


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]{3,}", text.lower())


def _split_sentences(text: str) -> list[str]:
    # Keep it conservative: avoid exploding on abbreviations.
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s and len(s.strip()) >= 40]


def split_into_sentences(text: str) -> list[str]:
    """Splits text into sentences, trying to be clever about abbreviations."""
    text = re.sub(r'([.!?])\s*([A-Z])', r'\1\n\2', text)
    text = re.sub(r'([.!?])\s*([a-z])', r'\1 \2', text)
    sentences = text.split('\n')
    return [s.strip() for s in sentences if s.strip()]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a.intersection(b)) / float(max(1, len(a.union(b))))


def _extract_heuristic_verified_facts(contents: list[dict[str, Any]]) -> tuple[list[str], float]:
    """
    Heuristic cross-source consistency:
    - Extract candidate sentences from each source.
    - For each candidate from source 0, check if a "similar" sentence exists
      in at least one other source.
    - Similarity uses token-set Jaccard over normalized content.
    """
    if not contents:
        return [], 0.0

    max_facts = int(os.getenv("WEB_VERIFY_MAX_FACTS", "8"))
    max_sentences_per_source = int(os.getenv("WEB_VERIFY_SENTENCES_PER_SOURCE", "30"))

    token_sets_by_source: list[list[tuple[str, set[str]]]] = []
    for c in contents:
        text = str(c.get("text") or "")
        sentences = _split_sentences(text)[:max_sentences_per_source]
        token_sets_by_source.append([(s, set(_tokenize(s))) for s in sentences])

    if not token_sets_by_source or not token_sets_by_source[0]:
        return [], 0.0

    base_sentences = token_sets_by_source[0]
    min_other_support = int(os.getenv("WEB_VERIFY_MIN_OTHER_SUPPORT", "1"))
    candidates: list[tuple[int, float, str]] = []
    for sent_idx, (sentence, s_tokens) in enumerate(base_sentences):
        if not s_tokens:
            continue

        max_jaccard = 0.0
        support_count = 0
        for other_source_tokens in token_sets_by_source[1:]:
            max_jaccard_other = 0.0
            for _, other_tokens in other_source_tokens:
                max_jaccard_other = max(max_jaccard_other, _jaccard(s_tokens, other_tokens))
            if max_jaccard_other > 0.6:
                support_count += 1
            max_jaccard = max(max_jaccard, max_jaccard_other)

        if support_count >= min_other_support:
            candidates.append((sent_idx, max_jaccard, sentence))

    # Sort by sentence order, then Jaccard
    candidates.sort(key=lambda x: (x[0], -x[1]))
    
    # Deduplicate and limit
    final_facts: list[str] = []
    seen_indices: set[int] = set()
    for sent_idx, _, sentence in candidates:
        if sent_idx not in seen_indices:
            final_facts.append(sentence)
            seen_indices.add(sent_idx)
        if len(final_facts) >= max_facts:
            break
            
    # Report the fraction of sentences from the first source that were verified
    total_base_sentences = len(base_sentences)
    verified_fraction = len(final_facts) / total_base_sentences if total_base_sentences > 0 else 0.0

    return final_facts, verified_fraction


def verify_content(
    query: str, extracted_sources: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Adds a 'verified_facts' list to each source and returns a globally verified
    list of facts.
    """
    if not extracted_sources:
        return [], []

    # Phase 1: Heuristic fact extraction from the top source, cross-verified
    globally_verified_facts, _ = _extract_heuristic_verified_facts(extracted_sources)

    # Phase 2: Add verified facts to each source object for downstream use
    for source in extracted_sources:
        source["verified_facts"], _ = _extract_heuristic_verified_facts([source] + extracted_sources)

    return extracted_sources, globally_verified_facts


def _extract_text_from_source(source: dict) -> str:
    """
    Retrieval results use a nested structure:
      {anchor_node: {content, heading}, pedagogical_context: [{content, heading}, ...]}
    Plain dicts may also have a top-level 'text' or 'content' key.
    This helper normalises all of them into a single string.
    """
    # Plain text key (web sources, uploaded files)
    direct = str(source.get("text") or source.get("content") or "").strip()
    if direct:
        return direct

    # Retrieval result structure
    parts: list[str] = []
    anchor = source.get("anchor_node") or {}
    anchor_text = " ".join(filter(None, [
        str(anchor.get("heading") or ""),
        str(anchor.get("content") or ""),
    ]))
    if anchor_text.strip():
        parts.append(anchor_text)

    for node in source.get("pedagogical_context") or []:
        node_text = " ".join(filter(None, [
            str(node.get("heading") or ""),
            str(node.get("content") or ""),
        ]))
        if node_text.strip():
            parts.append(node_text)

    return " ".join(parts)


def map_claims_to_sources(claims: list[str], sources: list[dict]) -> list[dict]:
    """
    Maps each claim to the source that best supports it.
    Returns a list of dicts, each with 'claim', 'source', and 'score'.
    """
    claim_source_map = []
    for claim in claims:
        best_source = None
        max_score = 0.0
        claim_tokens = set(_tokenize(claim))
        for source in sources:
            source_text = _extract_text_from_source(source)
            if not source_text:
                continue
            source_sentences = split_into_sentences(source_text)
            for sentence in source_sentences:
                sentence_tokens = set(_tokenize(sentence))
                score = _jaccard(claim_tokens, sentence_tokens)
                if score > max_score:
                    max_score = score
                    best_source = source

        claim_source_map.append({
            "claim": claim,
            "source": _source_label(best_source) if best_source else None,
            "score": max_score
        })
    return claim_source_map


def _source_label(source: dict) -> str:
    """Return a human-readable label for a source dict."""
    # Web / upload sources
    if source.get("url"):
        return str(source["url"])
    # Retrieval result
    anchor = source.get("anchor_node") or {}
    heading = anchor.get("heading") or source.get("heading") or source.get("source")
    return str(heading) if heading else "unknown"


def compute_groundedness_metrics(claim_source_map: list[dict]) -> dict:
    """Computes groundedness score and unsupported claim rate."""
    if not claim_source_map:
        return {"groundedness_score": 0.0, "unsupported_claim_rate": 1.0}

    min_score = float(os.getenv("GROUNDING_MIN_JACCARD", "0.05"))
    supported_claims = [
        c for c in claim_source_map
        if c["source"] is not None and c["score"] >= min_score
    ]

    groundedness_score = len(supported_claims) / len(claim_source_map)
    unsupported_claim_rate = 1.0 - groundedness_score

    return {
        "groundedness_score": groundedness_score,
        "unsupported_claim_rate": unsupported_claim_rate
    }


def ground_claims(answer: str, sources: list[dict]) -> dict:
    """
    Performs claim-level grounding of a generated answer against a list of sources.

    ``sources`` may be retrieval result dicts (with ``anchor_node`` /
    ``pedagogical_context`` fields) or plain dicts with a ``text`` key.
    Both are handled transparently via ``_extract_text_from_source``.
    """
    claims = split_into_sentences(answer)

    claim_source_map = map_claims_to_sources(claims, sources)

    # Lowered threshold: Jaccard 0.05 avoids dropping single-token matches.
    min_score = float(os.getenv("GROUNDING_MIN_JACCARD", "0.05"))
    supported_claims = [
        c["claim"]
        for c in claim_source_map
        if c["source"] is not None and c["score"] >= min_score
    ]

    # Safety net: if the grounding filter drops EVERYTHING (e.g. very short
    # single-sentence answers where tokens partially overlap), return the
    # full answer rather than an empty string.
    grounded_answer = " ".join(supported_claims) if supported_claims else answer

    metrics = compute_groundedness_metrics(claim_source_map)

    return {
        "grounded_answer": grounded_answer,
        "claim_source_map": claim_source_map,
        "metrics": metrics
    }

