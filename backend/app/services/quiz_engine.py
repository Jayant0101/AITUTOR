"""
Quiz Engine Service
===================
Generates MCQ-format quizzes. Uses the LLM when an API key is available;
falls back to a deterministic template-based generator from the knowledge graph.

Usage:
    engine = QuizEngine(knowledge_graph=kg)
    batch  = engine.generate(topic="BM25", difficulty="medium", num_questions=5)
"""
from __future__ import annotations

import json
import os
import random
import re
import uuid
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store for generated quizzes (quiz_id -> MCQBatch dict).
# In production, persist to the DB. For now, this survives the process lifetime.
_QUIZ_STORE: dict[str, dict] = {}


def _next_quiz_id() -> str:
    """Generate a stable UUID-based quiz ID for session persistence."""
    return str(uuid.uuid4())


def _call_llm_for_mcq(
    topic: str,
    difficulty: str,
    num_questions: int,
    context: str,
    provider: str,
    openai_client: Any | None,
    gemini_model: Any | None,
    temperature: float,
) -> list[dict] | None:
    """
    Ask the configured LLM to generate MCQs as a JSON list.
    Returns list of raw dicts or None on failure.
    """
    difficulty_guidance = {
        "easy": "straightforward recall questions",
        "medium": "questions requiring understanding and application",
        "hard": "questions requiring deep analysis, comparison, or edge-case reasoning",
    }.get(difficulty, "mixed difficulty questions")

    prompt = f"""You are an educational quiz generator.

Topic: {topic}
Difficulty: {difficulty} ({difficulty_guidance})
Number of questions: {num_questions}

Reference material (use this as the authoritative knowledge source):
{context[:6000] if context else "(no reference material — use general knowledge about this topic)"}

Generate {num_questions} multiple-choice questions. Return ONLY a valid JSON array.
Each element MUST follow this exact schema:
{{
  "question": "Question text here?",
  "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
  "correct_index": 0,
  "explanation": "Brief explanation of why the answer is correct."
}}

Rules:
- correct_index is 0-based (0=first option, 1=second, etc.)
- No duplicate questions
- Options must be plausible (good distractors)
- Do not include "A)", "B)" prefixes in option text — just the text itself
- Return ONLY the JSON array, no markdown, no commentary
"""

    text_response: str | None = None
    logger.info(f"LLM MCQ generation starting for topic='{topic}', provider='{provider}'")
    start_time = time.time()
    try:
        if openai_client:
            completion = openai_client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                temperature=temperature,
                messages=[
                    {"role": "system", "content": "Return only valid JSON arrays."},
                    {"role": "user", "content": prompt},
                ],
                timeout=10,  # Phase 5: performance safety
            )
            text_response = completion.choices[0].message.content
        elif gemini_model:
            # Phase 5: Gemini doesn't have a direct timeout arg in generate_content
            # but we can use signal or just rely on the default. 
            # For stabilization, we'll try/except carefully.
            import google.api_core.exceptions
            try:
                completion = gemini_model.generate_content(
                    prompt, 
                    request_options={"timeout": 10}
                )
                text_response = completion.text
            except Exception as e:
                logger.warning(f"Gemini generation failed or timed out: {e}")
                return None
        
        duration = time.time() - start_time
        logger.info(f"LLM MCQ generation completed in {duration:.2f}s")
    except Exception as e:
        logger.warning(f"LLM MCQ generation failed after {time.time() - start_time:.2f}s: {e}")
        return None

    if not text_response:
        return None

    # Extract the JSON array from the response
    match = re.search(r"\[[\s\S]*\]", text_response)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else None
    except Exception:
        return None


def _build_template_mcq(
    topic: str,
    difficulty: str,
    num_questions: int,
    kg_nodes: list[dict],
) -> list[dict]:
    """
    Template-based MCQ generator used when no LLM is available.
    Produces questions from knowledge-graph node content.
    """
    questions: list[dict] = []
    nodes = [n for n in kg_nodes if n.get("content") and len(str(n["content"])) > 40]
    random.shuffle(nodes)

    for i, node in enumerate(nodes[:num_questions]):
        heading = node.get("heading", f"Concept {i + 1}")
        content = str(node.get("content", ""))

        # Build a simple "What best describes X?" question
        correct = content[:120].strip().rstrip(".")
        if not correct:
            continue

        distractors = [
            f"An unrelated concept in {topic}",
            f"A method that contradicts {heading}",
            f"The inverse of {heading}",
        ]
        options = [correct] + distractors
        random.shuffle(options)
        correct_idx = options.index(correct)

        questions.append({
            "question": f"Which of the following best describes '{heading}'?",
            "options": options,
            "correct_index": correct_idx,
            "explanation": f"'{heading}' is described as: {correct}.",
        })

    # Pad with generic questions if we don't have enough nodes
    while len(questions) < num_questions:
        idx = len(questions)
        questions.append({
            "question": f"Which statement about {topic} is most accurate? (Q{idx + 1})",
            "options": [
                f"{topic} is a core concept in modern AI systems.",
                f"{topic} has no practical applications.",
                f"{topic} was invented after 2020.",
                f"{topic} replaces all traditional algorithms.",
            ],
            "correct_index": 0,
            "explanation": f"{topic} is widely used in AI and information retrieval systems.",
        })

    return questions[:num_questions]


class QuizEngine:
    """
    Generates MCQ quiz batches from a topic and difficulty level.
    Uses the LLM (Gemini/OpenAI) when available; falls back to a template generator.
    """

    def __init__(self, knowledge_graph=None, learner=None) -> None:
        self.kg = knowledge_graph
        self.learner = learner
        self.provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        self._openai_client = None
        self._gemini_model = None
        self._configure_clients()

    def _configure_clients(self) -> None:
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if api_key:
                try:
                    from openai import OpenAI
                    self._openai_client = OpenAI(api_key=api_key)
                except Exception:
                    pass

        if self.provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if api_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    model_name = os.getenv("LLM_MODEL", "gemini-1.5-flash")
                    self._gemini_model = genai.GenerativeModel(model_name)
                except Exception:
                    pass

    def _get_topic_context(self, topic: str) -> tuple[str, list[dict]]:
        """Extract relevant context from the knowledge graph for this topic."""
        if not self.kg:
            return "", []

        topic_lower = topic.lower()
        matched_nodes: list[dict] = []
        for node_id, data in self.kg.graph.nodes(data=True):
            heading = str(data.get("heading", "")).lower()
            content = str(data.get("content", "")).lower()
            keywords = " ".join(data.get("keywords", [])).lower()
            if topic_lower in heading or topic_lower in content or topic_lower in keywords:
                node = dict(data)
                node["id"] = node_id
                matched_nodes.append(node)

        context = "\n\n".join(
            f"### {n.get('heading', '')}\n{n.get('content', '')}"
            for n in matched_nodes[:10]
        )
        return context, matched_nodes

    def generate(
        self,
        topic: str,
        difficulty: str = "medium",
        num_questions: int = 10,
    ) -> dict:
        """
        Generate a quiz batch and store it in the in-memory store.
        Returns the full quiz batch dict (matches MCQBatch schema).
        """
        context, kg_nodes = self._get_topic_context(topic)

        # Try LLM generation first
        raw_questions = _call_llm_for_mcq(
            topic=topic,
            difficulty=difficulty,
            num_questions=num_questions,
            context=context,
            provider=self.provider,
            openai_client=self._openai_client,
            gemini_model=self._gemini_model,
            temperature=self.temperature,
        )

        if not raw_questions:
            # Fall back to template generator
            raw_questions = _build_template_mcq(
                topic=topic,
                difficulty=difficulty,
                num_questions=num_questions,
                kg_nodes=kg_nodes,
            )

        # Normalise into MCQQuestion dicts
        questions = []
        for i, q in enumerate(raw_questions[:num_questions]):
            options = q.get("options", [])
            if len(options) < 4:
                options += ["(no option)"] * (4 - len(options))
            questions.append({
                "id": i + 1,
                "question": str(q.get("question", "")).strip(),
                "options": [str(o) for o in options[:4]],
                "correct_index": int(q.get("correct_index", 0)) % 4,
                "explanation": str(q.get("explanation", "")).strip(),
            })

        quiz_id = _next_quiz_id()
        batch = {
            "quiz_id": quiz_id,
            "topic": topic,
            "difficulty": difficulty,
            "questions": questions,
        }
        
        if self.learner:
            self.learner.save_generated_quiz(quiz_id, json.dumps(batch))
        else:
            _QUIZ_STORE[quiz_id] = batch
            
        return batch

    def grade(
        self,
        quiz_id: str,
        user_answers: list[int],
        time_taken: int,
    ) -> dict:
        """
        Grade a submitted quiz and return score + feedback.
        Returns a dict matching QuizSessionResult schema.
        """
        batch = None
        if self.learner:
            data = self.learner.get_generated_quiz(quiz_id)
            if data:
                batch = json.loads(data)
        
        if not batch:
            batch = _QUIZ_STORE.get(quiz_id)
            
        if not batch:
            raise ValueError(f"Quiz {quiz_id} not found.")

        questions = batch["questions"]
        total = len(questions)
        score = 0
        wrong_topics: list[str] = []

        for i, question in enumerate(questions):
            user_ans = user_answers[i] if i < len(user_answers) else -1
            if user_ans == question["correct_index"]:
                score += 1
            else:
                wrong_topics.append(question["question"][:60])

        percentage = round((score / max(total, 1)) * 100, 2)

        # Generate adaptive feedback
        if percentage >= 85:
            feedback = f"Excellent! You scored {percentage:.0f}%. Strong understanding of {batch['topic']}."
        elif percentage >= 60:
            feedback = (
                f"Good effort! You scored {percentage:.0f}%. "
                f"Review the following areas: {'; '.join(wrong_topics[:3])}."
            )
        else:
            feedback = (
                f"You scored {percentage:.0f}%. Consider revisiting {batch['topic']} fundamentals. "
                f"Weak areas: {'; '.join(wrong_topics[:5])}."
            )

        return {
            "quiz_id": quiz_id,
            "score": score,
            "total": total,
            "percentage": percentage,
            "time_taken": time_taken,
            "feedback": feedback,
            "topic": batch["topic"],
            "difficulty": batch["difficulty"],
        }
