from __future__ import annotations

import json
import os
from typing import Any

from app.teaching.teaching_agent import TeachingAgent

def evaluate_answer(query: str, answer: str, sources: list[dict]) -> dict:
    """
    Evaluates a generated answer using an LLM as a judge.
    """
    
    teacher = TeachingAgent()

    prompt = f"""
You are an impartial judge evaluating the quality of an answer to a question.
You must evaluate the answer based on the provided sources.
The evaluation should be based on the following criteria:
- Correctness: Is the answer factually correct based on the provided sources?
- Relevance: Is the answer relevant to the question?
- Completeness: Does the answer cover all aspects of the question?

Question: {query}

Sources:
{json.dumps(sources, indent=2)}

Answer: {answer}

Provide your evaluation as a JSON object with the following format:
{{
    "correctness": {{
        "score": <score from 1 to 5>,
        "reasoning": "<your reasoning>"
    }},
    "relevance": {{
        "score": <score from 1 to 5>,
        "reasoning": "<your reasoning>"
    }},
    "completeness": {{
        "score": <score from 1 to 5>,
        "reasoning": "<your reasoning>"
    }}
}}
"""
    
    llm_payload = teacher._generate_with_llm(
        query=prompt,
        mode="evaluation",
        context_items=[],
        mastery_by_node={},
        verified_facts=[],
    )

    if llm_payload:
        return llm_payload
    else:
        return {
            "correctness": {"score": 0, "reasoning": "Error generating evaluation."},
            "relevance": {"score": 0, "reasoning": "Error generating evaluation."},
            "completeness": {"score": 0, "reasoning": "Error generating evaluation."},
        }
