from __future__ import annotations

import json
import os
import re
from typing import Any


class TeachingAgent:
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        self.model = os.getenv("LLM_MODEL", "").strip()
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        self._openai_client = None
        self._gemini_model = None
        self._configure_clients()

    def _configure_clients(self) -> None:
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                return
            try:
                from openai import OpenAI

                self._openai_client = OpenAI(api_key=api_key)
                if not self.model:
                    self.model = "gpt-4o-mini"
            except Exception:
                self._openai_client = None

        if self.provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                return
            try:
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                self._gemini_model = genai.GenerativeModel(
                    self.model or "gemini-1.5-flash"
                )
                if not self.model:
                    self.model = "gemini-1.5-flash"
            except Exception:
                self._gemini_model = None

    def generate(
        self,
        query: str,
        retrieval_results: list[dict],
        mastery_by_node: dict[str, dict],
        mode: str = "socratic",
    ) -> dict:
        context_items = self._flatten_context(retrieval_results)
        citations = self._build_citations(context_items)
        focus_node_id = context_items[0]["id"] if context_items else None
        context_terms = self._context_terms(context_items)

        llm_payload = self._generate_with_llm(
            query=query,
            mode=mode,
            context_items=context_items,
            mastery_by_node=mastery_by_node,
        )
        if llm_payload:
            if llm_payload.get("mode") == "socratic":
                grounded_text, ungrounded = self._ground_text(
                    llm_payload.get("text", ""), context_terms
                )
                if grounded_text:
                    llm_payload["text"] = grounded_text
                llm_payload["ungrounded_sentences"] = ungrounded
            llm_payload["citations"] = citations
            if focus_node_id:
                llm_payload["focus_node_id"] = focus_node_id
            return llm_payload

        if mode == "quiz":
            quiz_payload = self._offline_quiz(
                query=query,
                context_items=context_items,
                mastery_by_node=mastery_by_node,
            )
            quiz_payload["citations"] = citations
            if focus_node_id:
                quiz_payload["focus_node_id"] = focus_node_id
            return quiz_payload

        response_text = self._offline_socratic(
            query=query,
            context_items=context_items,
            mastery_by_node=mastery_by_node,
        )
        grounded_text, ungrounded = self._ground_text(response_text, context_terms)
        return {
            "mode": "socratic",
            "text": grounded_text or response_text,
            "citations": citations,
            "focus_node_id": focus_node_id,
            "ungrounded_sentences": ungrounded,
        }

    def _generate_with_llm(
        self,
        query: str,
        mode: str,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
    ) -> dict | None:
        if not context_items:
            return None

        context_lines = []
        for item in context_items[:8]:
            context_lines.append(
                f"[{item['id']}] {item.get('heading', 'Untitled')}: {item.get('content', '')}"
            )
        mastery_lines = []
        for node_id, state in mastery_by_node.items():
            mastery_lines.append(
                f"{node_id} mastery={float(state.get('mastery', 0.25)):.2f}"
            )

        prompt = f"""
You are an AI tutor. Use only the provided context.
Mode: {mode}
Student query: {query}

Context:
{chr(10).join(context_lines)}

Learner mastery:
{chr(10).join(mastery_lines) if mastery_lines else "No prior mastery data."}

Return strict JSON:
- For socratic mode: {{"mode":"socratic","text":"...", "follow_up_question":"..."}}
- For quiz mode: {{"mode":"quiz","question":"...","expected_answer":"...","difficulty":"easy|medium|hard"}}
"""

        text_response = None
        try:
            if self._openai_client:
                completion = self._openai_client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": "Return only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                )
                text_response = completion.choices[0].message.content
            elif self._gemini_model:
                completion = self._gemini_model.generate_content(prompt)
                text_response = completion.text
        except Exception:
            return None

        if not text_response:
            return None

        try:
            parsed = json.loads(self._extract_json_block(text_response))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _flatten_context(self, retrieval_results: list[dict]) -> list[dict]:
        flattened: list[dict] = []
        seen: set[str] = set()
        for result in retrieval_results:
            anchor = result.get("anchor_node", {})
            anchor_id = result.get("anchor_node_id")
            if anchor_id and anchor_id not in seen:
                merged_anchor = dict(anchor)
                merged_anchor["id"] = anchor_id
                flattened.append(merged_anchor)
                seen.add(anchor_id)

            for node in result.get("pedagogical_context", []):
                node_id = node.get("id")
                if node_id and node_id not in seen:
                    flattened.append(node)
                    seen.add(node_id)
        return flattened

    def _build_citations(self, context_items: list[dict]) -> list[dict]:
        citations: list[dict] = []
        for item in context_items[:6]:
            citations.append(
                {
                    "node_id": item.get("id"),
                    "heading": item.get("heading", "Untitled"),
                    "source": item.get("source", "unknown"),
                }
            )
        return citations

    def _context_terms(self, context_items: list[dict]) -> set[str]:
        terms: set[str] = set()
        for item in context_items[:10]:
            heading = item.get("heading", "")
            terms.update(self._tokens(heading))
            for keyword in item.get("keywords", []) or []:
                terms.update(self._tokens(str(keyword)))
        return terms

    def _offline_socratic(
        self,
        query: str,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
    ) -> str:
        if not context_items:
            return (
                "I could not find grounded course context for that question yet. "
                "Try rephrasing with key terms from your study material."
            )

        focus = context_items[0]
        focus_mastery = mastery_by_node.get(focus["id"], {}).get("mastery", 0.25)
        summary = self._first_sentence(focus.get("content", ""))

        misconception_hint = ""
        if self._query_has_misconception_signal(query):
            misconception_hint = (
                "A common misconception here is mixing related terms without checking prerequisites. "
            )

        if focus_mastery < 0.4:
            level_hint = (
                "Let us start from fundamentals and build one step at a time. "
            )
        elif focus_mastery > 0.75:
            level_hint = "You seem strong here, so we can push to a deeper connection. "
        else:
            level_hint = "We can reinforce the core idea and then apply it. "

        follow_up = (
            f"What is one prerequisite idea you think {focus.get('heading', 'this concept')} depends on?"
        )
        return (
            f"{level_hint}{misconception_hint}"
            f"Focus concept: {focus.get('heading', 'Untitled')}. "
            f"Grounded explanation: {summary} "
            f"Socratic check: {follow_up}"
        ).strip()

    def _offline_quiz(
        self,
        query: str,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
    ) -> dict:
        if not context_items:
            return {
                "mode": "quiz",
                "question": "No context available yet. Ask a content question first.",
                "expected_answer": "",
                "difficulty": "easy",
            }

        focus = context_items[0]
        focus_mastery = float(mastery_by_node.get(focus["id"], {}).get("mastery", 0.25))
        difficulty = "easy" if focus_mastery < 0.35 else "medium" if focus_mastery < 0.7 else "hard"

        summary = self._first_sentence(focus.get("content", ""))
        question = (
            f"In your own words, explain '{focus.get('heading', 'this topic')}' "
            f"and why it matters in the current lesson."
        )
        return {
            "mode": "quiz",
            "question": question,
            "expected_answer": summary,
            "difficulty": difficulty,
        }

    def _extract_json_block(self, text: str) -> str:
        match = re.search(r"\{[\s\S]*\}", text)
        return match.group(0) if match else text

    def _first_sentence(self, text: str) -> str:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return "The core details are in the retrieved course context."
        sentence = re.split(r"(?<=[.!?])\s+", normalized)[0]
        return sentence[:300]

    def _ground_text(self, text: str, context_terms: set[str]) -> tuple[str, list[str]]:
        if not text.strip():
            return "", []
        if not context_terms:
            return text, []

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        grounded = []
        ungrounded = []
        for sentence in sentences:
            tokens = set(self._tokens(sentence))
            if tokens.intersection(context_terms):
                grounded.append(sentence)
            else:
                ungrounded.append(sentence)

        grounded_text = " ".join(grounded).strip()
        return grounded_text, ungrounded

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]{3,}", text.lower())

    def _query_has_misconception_signal(self, query: str) -> bool:
        lowered = query.lower()
        signals = [
            "i think",
            "isn't",
            "isnt",
            "so that means",
            "does this mean",
            "always",
            "never",
        ]
        return any(signal in lowered for signal in signals)
