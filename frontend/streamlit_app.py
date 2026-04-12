from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


DEFAULT_API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def call_api(method: str, url: str, **kwargs) -> requests.Response:
    timeout = kwargs.pop("timeout", 30)
    return requests.request(method=method, url=url, timeout=timeout, **kwargs)


def render_error(message: str) -> None:
    st.error(message)


st.set_page_config(
    page_title="Vectorless AI Learning Assistant",
    page_icon=":books:",
    layout="wide",
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_quiz" not in st.session_state:
    st.session_state.last_quiz = None

st.title("Vectorless Graph-based AI Learning Assistant")
st.caption("Phase 1-4: BM25 + Graph traversal + Learner tracking + Socratic teaching")

with st.sidebar:
    st.header("Configuration")
    api_base = st.text_input("Backend URL", value=DEFAULT_API_BASE).rstrip("/")
    user_id = st.text_input("User ID", value="demo-user")
    mode = st.selectbox("Mode", options=["socratic", "quiz"])
    top_k = st.slider("Top K retrieval anchors", min_value=1, max_value=10, value=3)

    if st.button("Reload Knowledge Base", use_container_width=True):
        try:
            response = call_api("POST", f"{api_base}/ingest", json={})
            response.raise_for_status()
            st.success("Knowledge base reloaded.")
        except Exception as exc:
            render_error(f"Ingest failed: {exc}")

    if st.button("Refresh Progress", use_container_width=True):
        try:
            response = call_api("GET", f"{api_base}/learner/{user_id}/progress")
            response.raise_for_status()
            st.session_state.progress_payload = response.json()
        except Exception as exc:
            render_error(f"Progress fetch failed: {exc}")

query = st.text_input("Ask a learning question")
ask_clicked = st.button("Ask", use_container_width=True)

if ask_clicked and query.strip():
    try:
        payload = {
            "user_id": user_id,
            "query": query.strip(),
            "mode": mode,
            "top_k": top_k,
        }
        response = call_api("POST", f"{api_base}/chat", json=payload)
        response.raise_for_status()
        data = response.json()
        st.session_state.chat_history.append(data)
        if data.get("mode") == "quiz":
            st.session_state.last_quiz = data["result"]
    except Exception as exc:
        render_error(f"Chat request failed: {exc}")

st.subheader("Chat")
for turn in reversed(st.session_state.chat_history[-10:]):
    result: dict[str, Any] = turn.get("result", {})
    with st.container(border=True):
        st.markdown(f"**Query:** {turn.get('query', '')}")
        if result.get("mode") == "quiz":
            st.markdown(f"**Quiz Question:** {result.get('question', '')}")
            st.caption(f"Difficulty: {result.get('difficulty', 'unknown')}")
        else:
            st.markdown(result.get("text", "_No response text_"))

        citations = result.get("citations", [])
        if citations:
            with st.expander("Grounding citations"):
                for citation in citations:
                    st.write(
                        f"- [{citation.get('node_id')}] {citation.get('heading')} "
                        f"({citation.get('source')})"
                    )

if st.session_state.last_quiz:
    quiz = st.session_state.last_quiz
    st.subheader("Submit Quiz Answer")
    st.write(quiz.get("question", "No quiz question available."))
    quiz_answer = st.text_area("Your answer", height=120)
    if st.button("Submit Quiz", use_container_width=True):
        try:
            submit_payload = {
                "user_id": user_id,
                "node_id": quiz.get("focus_node_id") or quiz.get("node_id") or "unknown-node",
                "question": quiz.get("question", ""),
                "expected_answer": quiz.get("expected_answer", ""),
                "user_answer": quiz_answer,
                "difficulty": quiz.get("difficulty", "medium"),
            }
            response = call_api("POST", f"{api_base}/quiz/submit", json=submit_payload)
            response.raise_for_status()
            data = response.json()
            if data.get("is_correct"):
                st.success("Marked as correct.")
            else:
                st.warning("Marked as incorrect. Review the concept and try again.")
            st.json(data)
        except Exception as exc:
            render_error(f"Quiz submission failed: {exc}")

st.subheader("Learner Progress")
progress_payload = st.session_state.get("progress_payload")
if progress_payload:
    st.metric("Tracked Nodes", progress_payload.get("tracked_nodes", 0))
    st.metric(
        "Average Mastery",
        f"{float(progress_payload.get('average_mastery', 0.0)):.2f}",
    )
    weak_nodes = progress_payload.get("weak_nodes", [])
    if weak_nodes:
        st.write("Weak topics:")
        st.dataframe(weak_nodes, use_container_width=True)
    due = progress_payload.get("due_for_review", [])
    if due:
        st.write("Due for review:")
        st.dataframe(due, use_container_width=True)
else:
    st.info("Use 'Refresh Progress' in the sidebar to load learner metrics.")
