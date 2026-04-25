from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Iterator

from openai import OpenAI

from ntu_dual_guide_rag.models import StructuredModelAnswer


STRUCTURED_ANSWER_SCHEMA = {
    "name": "rag_answer",
    "schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["answered", "unknown"],
                "description": "Whether the provided context is sufficient to answer the user's question.",
            },
            "answer": {
                "type": "string",
                "description": "The final Traditional Chinese answer shown to the user. If status is unknown, explain briefly why.",
            },
        },
        "required": ["status", "answer"],
        "additionalProperties": False,
    },
    "strict": True,
}


def create_text_response(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> str:
    response = get_client(api_key).responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        text={"format": {"type": "text"}},
    )
    return extract_output_text(response).strip()


def create_structured_answer(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> StructuredModelAnswer:
    response = get_client(api_key).responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        text={
            "format": {
                "type": "json_schema",
                "name": STRUCTURED_ANSWER_SCHEMA["name"],
                "schema": STRUCTURED_ANSWER_SCHEMA["schema"],
                "strict": STRUCTURED_ANSWER_SCHEMA["strict"],
            }
        },
    )
    refusal = extract_refusal_text(response)
    if refusal:
        return StructuredModelAnswer(status="unknown", answer=refusal.strip())

    output_text = extract_output_text(response)
    if not output_text:
        raise RuntimeError("Responses API returned no structured output text.")
    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Responses API returned invalid structured JSON: {0}".format(output_text)
        ) from exc
    return StructuredModelAnswer.from_dict(payload)


def create_structured_response(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
    schema_name: str,
    schema: dict[str, Any],
    strict: bool = True,
) -> dict[str, Any]:
    """Call the Responses API with a json_schema format and return the parsed JSON dict."""
    response = get_client(api_key).responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": strict,
            }
        },
    )
    output_text = extract_output_text(response)
    if not output_text:
        raise RuntimeError("Responses API returned no structured output text.")
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Responses API returned invalid structured JSON: {0}".format(output_text)
        ) from exc


def stream_text_response(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> Iterator[tuple[str, str]]:
    """Stream a text-format response.

    Yields:
      ("reasoning", delta) — reasoning summary chunks (only emitted by reasoning models)
      ("delta", delta)     — visible answer token chunks
      ("done", full_text)  — final concatenated answer text, once at the end
    """
    client = get_client(api_key)
    debug_stream = os.environ.get("RAG_STREAM_DEBUG") == "1"
    with client.responses.stream(
        model=model,
        instructions=instructions,
        input=user_input,
        text={"format": {"type": "text"}},
        reasoning={"summary": "detailed"},
    ) as stream:
        for event in stream:
            event_type = getattr(event, "type", "")
            if debug_stream:
                print("[stream] event:", event_type, flush=True)
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    yield ("delta", delta)
            elif event_type == "response.reasoning_summary_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    yield ("reasoning", delta)
        final = stream.get_final_response()
    yield ("done", extract_output_text(final).strip())


def extract_output_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "output_text":
                value = getattr(content, "text", "") or ""
                if value:
                    parts.append(value)
    return "\n".join(parts)


def extract_refusal_text(response: Any) -> str | None:
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "refusal":
                refusal = getattr(content, "refusal", None)
                if refusal:
                    return str(refusal)
    return None


@lru_cache(maxsize=4)
def get_client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        timeout=get_responses_timeout_seconds(),
        max_retries=get_responses_max_retries(),
    )


def get_responses_timeout_seconds() -> float:
    return float(os.environ.get("OPENAI_RESPONSES_TIMEOUT_SECONDS", "120"))


def get_responses_max_retries() -> int:
    return int(os.environ.get("OPENAI_RESPONSES_MAX_RETRIES", "2"))
