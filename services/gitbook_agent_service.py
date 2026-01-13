"""GitBook RAG agent orchestration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import dspy

from agents.agent_config import get_agent_by_name
from modules.signatures import GitBookAnswerSignature
from services.gitbook_processor import gitbook_processor

logger = logging.getLogger(__name__)

AGENT_NAME = "gitbook_rag_copilot"


def _prepare_snippets(documents: List[Dict], max_chars: int = 600) -> List[str]:
    snippets = []
    for idx, doc in enumerate(documents, 1):
        title = doc.get("title") or "Untitled"
        url = doc.get("url") or ""
        text = (doc.get("text") or "").replace("\r", " ")
        excerpt = text[:max_chars].strip()
        snippets.append(
            f"[{idx}] Title: {title}\nURL: {url}\nExcerpt: {excerpt}"
        )
    return snippets


def _build_references(documents: List[Dict]) -> List[str]:
    references = []
    for idx, doc in enumerate(documents, 1):
        title = doc.get("title") or "Untitled"
        url = doc.get("url") or ""
        references.append(f"[{idx}] {title} — {url}")
    return references


def generate_gitbook_answer(query: str, limit: int = 4) -> Dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("Query must not be empty")

    agent_config = get_agent_by_name(AGENT_NAME)
    search_result = gitbook_processor.search_documents(query, limit)
    documents = search_result.result

    if not documents:
        return {
            "answer": "## Direct Answer\nI couldn't find anything for that question.\n\n## Key Details\n- No GitBook passages matched the query.\n\n## References\n*None*",
            "references": [],
            "documents": []
        }

    snippets = _prepare_snippets(documents)
    references = _build_references(documents)

    instructions = "\n".join(agent_config.query_instructions + [
        "Follow the template strictly:",
        "## Direct Answer\n<2-3 sentence summary>",
        "## Key Details\n- Bullet fact with inline [number]\n- Another fact",
        "## References\n[List every reference as [n] Title — URL]"
    ])

    predictor = dspy.Predict(GitBookAnswerSignature)
    response = predictor(
        system_prompt=agent_config.system_prompt,
        user_question=query,
        snippets=snippets,
        format_instructions=instructions
    )

    answer_text = response.answer_markdown.strip() if response and getattr(response, 'answer_markdown', None) else ""
    if not answer_text:
        answer_text = "## Direct Answer\nI'm unable to draft a summary right now.\n\n## Key Details\n- Try again shortly.\n\n## References\n*None*"

    # Remove the references section if the model already rendered one; we send a structured list separately.
    if "## References" in answer_text:
        answer_text = answer_text.split("## References", 1)[0].strip()

    return {
        "answer": answer_text,
        "references": references,
        "documents": documents
    }
