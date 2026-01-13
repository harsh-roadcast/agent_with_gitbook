"""GitBook RAG agent orchestration."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterator, List

import dspy

from agents.agent_config import get_agent_by_name
from modules.signatures import GitBookAnswerSignature
from services.gitbook_processor import gitbook_processor

logger = logging.getLogger(__name__)

AGENT_NAME = "gitbook_rag_copilot"
LONG_FORM_KEYWORDS = (
    "detailed",
    "long",
    "longer",
    "full",
    "comprehensive",
    "in depth",
    "in-depth",
    "deep dive",
    "extensive",
    "elaborate",
    "explain in detail",
    "more detail",
    "dive deep"
)


def _wants_detailed_answer(query: str) -> bool:
    if not query:
        return False

    normalized = query.lower()
    for keyword in LONG_FORM_KEYWORDS:
        if keyword in normalized or re.search(rf"\b{re.escape(keyword)}\b", normalized):
            return True
    return False


def _enforce_word_limit(markdown: str, limit: int = 150) -> str:
    if limit <= 0:
        return markdown

    words_used = 0
    lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
            continue

        if stripped.startswith("## "):
            lines.append(line)
            continue

        prefix = ""
        body = stripped
        if stripped.startswith("- "):
            prefix = "- "
            body = stripped[2:].strip()

        tokens = body.split()
        available = limit - words_used
        if available <= 0:
            break

        if len(tokens) <= available:
            lines.append(f"{prefix}{body}")
            words_used += len(tokens)
        else:
            truncated = " ".join(tokens[:available]) + "…"
            lines.append(f"{prefix}{truncated}")
            words_used = limit
            break

    return "\n".join(lines).strip()


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


def _chunk_answer_text(answer: str, chunk_size: int = 280) -> Iterator[str]:
    """Yield small slices of the markdown answer for streaming clients."""
    sanitized = (answer or "").strip()
    if not sanitized:
        return

    start = 0
    length = len(sanitized)
    while start < length:
        end = min(start + chunk_size, length)
        yield sanitized[start:end]
        start = end


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
        "## References\n[List every reference as [n] Title — URL]",
        "Keep the overall response under 150 words unless the user explicitly asks for a detailed or long explanation."
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

    if not _wants_detailed_answer(query):
        answer_text = _enforce_word_limit(answer_text, 150)

    return {
        "answer": answer_text,
        "references": references,
        "documents": documents
    }


def stream_gitbook_answer(query: str, limit: int = 4) -> Iterator[Dict[str, Any]]:
    """Yield incremental GitBook answer events suitable for StreamingResponse."""
    yield {"type": "status", "message": "Collecting GitBook passages"}
    result = generate_gitbook_answer(query, limit)

    answer_text = result.get("answer", "")
    references = result.get("references", [])
    documents = result.get("documents", [])

    has_chunk = False
    for chunk in _chunk_answer_text(answer_text):
        has_chunk = True
        yield {"type": "answer_chunk", "delta": chunk}

    if not has_chunk:
        yield {"type": "answer_chunk", "delta": "I couldn't find anything for that query."}

    yield {
        "type": "references",
        "references": references,
        "documents": documents
    }

    yield {"type": "done"}
