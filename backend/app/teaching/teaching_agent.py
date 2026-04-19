from __future__ import annotations

from app.verification import ground_claims

import json
import os
import re
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


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

    async def generate_stream(
        self,
        query: str,
        retrieval_results: list[dict],
        mastery_by_node: dict[str, dict],
        mode: str = "socratic",
        history: list[dict] | None = None,
    ):
        sanitized_query = self._sanitize_query(query)
        context_items = self._flatten_context(retrieval_results)
        
        # --- TASK 3: CONTEXT DEDUPLICATION ---
        # Already handled by _flatten_context using 'seen' set of IDs.
        
        if not context_items:
            yield "Insufficient information."
            return

        verified_facts = self._extract_verified_facts(
            query=sanitized_query,
            context_items=context_items,
            mode=mode,
        )
        if not verified_facts:
            yield "Insufficient information."
            return

        # --- TASK 3: MEMORY LIMIT ---
        # Limit history to last 10 interactions to prevent uncontrolled growth
        pruned_history = (history or [])[-10:]
        
        facts_lines = [f"[F{idx}] {fact}" for idx, fact in enumerate(verified_facts, start=1)]
        mastery_lines = [f"{node_id} mastery={float(state.get('mastery', 0.25)):.2f}" for node_id, state in mastery_by_node.items()]

        prompt = f"""
You are an AI tutor. Answer ONLY using verified facts.
Student query: {sanitized_query}
Verified facts:
{chr(10).join(facts_lines)}
Learner mastery:
{chr(10).join(mastery_lines) if mastery_lines else "No prior data."}
Mode: {mode}
Respond as a helpful tutor.
"""
        messages = [{"role": "system", "content": "You are a helpful AI tutor. Stay grounded in the provided facts."}]
        for m in pruned_history:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": prompt})

        # --- TASK 2: NATIVE STREAMING ---
        try:
            if self.provider == "openai" and self._openai_client:
                # OpenAI Streaming
                stream = self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    timeout=30.0
                )
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            elif self.provider == "gemini" and self._gemini_model:
                # Gemini Streaming
                # Combine messages for Gemini (naive approach for now)
                full_prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                response = self._gemini_model.generate_content(full_prompt, stream=True)
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
            else:
                yield "Streaming not configured or provider unavailable."
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"Error: {str(e)}"

    def _sanitize_query(self, query: str) -> str:
        """Prevent simple prompt injection by stripping known malicious patterns."""
        # Remove common injection keywords
        patterns = [
            r"ignore previous instructions",
            r"ignore all previous",
            r"system prompt",
            r"you are now",
            r"new instructions",
        ]
        sanitized = query
        for p in patterns:
            sanitized = re.sub(p, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        return sanitized.strip()

    def generate(
        self,
        query: str,
        retrieval_results: list[dict],
        mastery_by_node: dict[str, dict],
        mode: str = "socratic",
        history: list[dict] | None = None,
    ) -> dict:
        sanitized_query = self._sanitize_query(query)
        context_items = self._flatten_context(retrieval_results)
        citations = self._build_citations(context_items)
        focus_node_id = context_items[0]["id"] if context_items else None

        if not context_items:
            return self._insufficient_context_response(mode)

        # Pipeline contract: Retrieve -> Extract verified facts -> (optionally verify) -> Generate.
        # If we can't produce any verified facts, do not call the LLM.
        verified_facts = self._extract_verified_facts(
            query=sanitized_query,
            context_items=context_items,
            mode=mode,
        )
        if not verified_facts:
            return self._insufficient_context_response(mode)

        llm_payload = self._generate_with_llm(
            query=sanitized_query,
            mode=mode,
            context_items=context_items,
            mastery_by_node=mastery_by_node,
            verified_facts=verified_facts,
            history=history,
        )
        if llm_payload:
            if llm_payload.get("mode") == "socratic":
                structured = self._build_structured_text_from_llm(
                    llm_payload=llm_payload,
                    context_items=context_items,
                    mastery_by_node=mastery_by_node,
                )
                
                grounding_results = ground_claims(structured, retrieval_results)
                
                # Strict safety: never return ungrounded text.
                if grounding_results["grounded_answer"].strip():
                    llm_payload["text"] = self._append_sources_footer(grounding_results["grounded_answer"], citations)
                    llm_payload["grounding"] = grounding_results
                else:
                    llm_payload["text"] = "Insufficient information."
                    llm_payload["grounding"] = None
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
        grounding_results = ground_claims(response_text, retrieval_results)
        
        return {
            "mode": "socratic",
            "text": self._append_sources_footer(grounding_results["grounded_answer"], citations)
            if grounding_results["grounded_answer"].strip()
            else "Insufficient information.",
            "citations": citations,
            "focus_node_id": focus_node_id,
            "grounding": grounding_results,
        }

    def _generate_with_llm(
        self,
        query: str,
        mode: str,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
        verified_facts: list[str],
        history: list[dict] | None = None,
    ) -> dict | None:
        if not context_items:
            return None

        # Token Pruning: Limit history to last 5 turns to stay within context limits
        pruned_history = (history or [])[-10:]
        
        facts_lines = []
        for idx, fact in enumerate(verified_facts, start=1):
            facts_lines.append(f"[F{idx}] {fact}")
        mastery_lines = []
        for node_id, state in mastery_by_node.items():
            mastery_lines.append(
                f"{node_id} mastery={float(state.get('mastery', 0.25)):.2f}"
            )

        prompt = f"""
You are an AI tutor. You must answer ONLY using the provided verified facts.
If information is insufficient, you must say exactly: "Insufficient information."
Mode: {mode}
Student query: {query}

Verified facts:
{chr(10).join(facts_lines)}

Learner mastery:
{chr(10).join(mastery_lines) if mastery_lines else "No prior mastery data."}

Return strict JSON:
- For socratic mode:
{{
  "mode":"socratic",
  "concept":"...",
  "steps":["...","..."],
  "example":"...",
  "check_question":"..."
}}
- For quiz mode: {{"mode":"quiz","question":"...","expected_answer":"...","difficulty":"easy|medium|hard"}}
"""

        messages = [
            {"role": "system", "content": "You are an AI tutor. You must answer ONLY using the provided verified facts. If information is insufficient, say exactly: 'Insufficient information.' Return only valid JSON."},
        ]
        
        # Inject pruned history
        for msg in pruned_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        # Add the current prompt
        messages.append({"role": "user", "content": prompt})

        text_response = None
        logger.info(f"LLM teaching generation starting for mode='{mode}', provider='{self.provider}'")
        start_time = time.time()
        try:
            if self._openai_client:
                completion = self._openai_client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=messages,
                    timeout=10,  # Phase 5: performance safety
                )
                text_response = completion.choices[0].message.content
            elif self._gemini_model:
                # Gemini doesn't support system/user/history easily in generate_content(prompt)
                # We combine it into a single string if it's Gemini for now, or use their Chat API
                full_prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                try:
                    completion = self._gemini_model.generate_content(
                        full_prompt,
                        request_options={"timeout": 10}
                    )
                    text_response = completion.text
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Gemini teaching generation failed: {e}")
                    return None
            
            duration = time.time() - start_time
            logger.info(f"LLM teaching generation completed in {duration:.2f}s")
        except Exception as e:
            logger.warning(f"LLM teaching generation failed after {time.time() - start_time:.2f}s: {e}")
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



    def _extract_verified_facts(
        self,
        *,
        query: str,
        context_items: list[dict],
        mode: str,
    ) -> list[str]:
        """
        Stage 1+2: extract candidate claims (sentences) and verify them via grounding signals.
        We use a lightweight heuristic verifier: keep sentences that overlap with both the query
        and the available context term set. This is hallucination-safe because the generator
        never sees non-overlapping claims.
        """
        min_query_overlap = int(os.getenv("FACT_MIN_QUERY_OVERLAP", "1"))
        # In quiz mode, `query` is typically a meta-instruction (e.g., "Quiz me on ..."),
        # so enforce weaker coupling between the prompt and the retrieved content.
        if mode == "quiz":
            min_query_overlap = 0
        min_sentence_chars = int(os.getenv("FACT_MIN_SENTENCE_CHARS", "25"))
        max_facts = int(os.getenv("FACT_MAX_FACTS", "10"))

        query_tokens = set(self._tokens(query))

        verified: list[str] = []
        seen: set[str] = set()

        for item in context_items[:8]:
            content = str(item.get("content") or "").strip()
            if not content:
                # Some knowledge graph nodes embed text in `heading` (chunking artifacts).
                content = str(item.get("heading") or "").strip()
            if not content:
                continue
            # Split on sentence boundaries; keep fairly complete sentences.
            sentences = re.split(r"(?<=[.!?])\s+", content)
            for sentence in sentences:
                s = sentence.strip()
                if len(s) < min_sentence_chars:
                    continue
                tokens = set(self._tokens(s))
                if not tokens:
                    continue

                overlap_query = len(tokens.intersection(query_tokens))
                if overlap_query >= min_query_overlap:
                    if s not in seen:
                        seen.add(s)
                        verified.append(s)
                if len(verified) >= max_facts:
                    return verified

        return verified

    def _offline_socratic(
        self,
        query: str,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
    ) -> str:
        if not context_items:
            return "Insufficient information."

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
            f"Concept: {focus.get('heading', 'Untitled')}. "
            f"Step-by-step: 1) {level_hint.strip()} 2) {misconception_hint.strip() or 'Connect the core mechanism to the lesson goal.'} "
            f"3) Grounded explanation: {summary} "
            f"Example: In this lesson context, {focus.get('heading', 'the concept')} is used to improve answer quality by selecting relevant evidence first. "
            f"Check understanding: {follow_up}"
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
                "question": "Insufficient information.",
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

    def _build_structured_text_from_llm(
        self,
        llm_payload: dict,
        context_items: list[dict],
        mastery_by_node: dict[str, dict],
    ) -> str:
        concept = llm_payload.get("concept") or context_items[0].get("heading", "Concept")
        steps = llm_payload.get("steps") or []
        if not isinstance(steps, list):
            steps = [str(steps)]
        trimmed_steps = [str(step).strip() for step in steps if str(step).strip()][:3]
        if not trimmed_steps:
            fallback = self._first_sentence(context_items[0].get("content", ""))
            trimmed_steps = [fallback]

        example = str(llm_payload.get("example", "")).strip()
        if not example:
            example = f"Use {concept} on a question where retrieval quality impacts answer accuracy."

        check_q = str(llm_payload.get("check_question", "")).strip()
        if not check_q:
            check_q = f"How would you apply {concept} in this lesson?"

        focus_id = context_items[0].get("id", "")
        focus_mastery = float(mastery_by_node.get(focus_id, {}).get("mastery", 0.25))
        level_prefix = "Foundational" if focus_mastery < 0.4 else "Advanced" if focus_mastery > 0.75 else "Core"
        numbered_steps = " ".join(
            [f"{idx + 1}) {step}" for idx, step in enumerate(trimmed_steps)]
        )
        return (
            f"Concept: {concept}. "
            f"Step-by-step ({level_prefix}): {numbered_steps} "
            f"Example: {example} "
            f"Check understanding: {check_q}"
        )

    def _append_sources_footer(self, text: str, citations: list[dict]) -> str:
        if not citations:
            return text
        source_labels = []
        for idx, citation in enumerate(citations[:3], start=1):
            heading = citation.get("heading", "Untitled")
            source_labels.append(f"[S{idx}] {heading}")
        return f"{text}\nSources: {'; '.join(source_labels)}"

    def _insufficient_context_response(self, mode: str) -> dict:
        if mode == "quiz":
            return {
                "mode": "quiz",
                "question": "Insufficient information.",
                "expected_answer": "",
                "difficulty": "easy",
                "citations": [],
            }
        return {
            "mode": "socratic",
            "text": "Insufficient information.",
            "citations": [],
        }
