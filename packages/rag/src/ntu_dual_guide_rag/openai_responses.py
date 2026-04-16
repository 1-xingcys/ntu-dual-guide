from __future__ import annotations

import json
from typing import Any
from urllib import error
from urllib import request

from ntu_dual_guide_rag.models import StructuredModelAnswer


RESPONSES_API_URL = "https://api.openai.com/v1/responses"
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
    payload = {
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "text": {
            "format": {
                "type": "text",
            }
        },
    }
    body = post_responses_request(
        api_key=api_key,
        payload=payload,
    )
    return extract_output_text(body)


def create_structured_answer(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
) -> StructuredModelAnswer:
    payload = {
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "text": {
            "format": {
                "type": "json_schema",
                "name": STRUCTURED_ANSWER_SCHEMA["name"],
                "schema": STRUCTURED_ANSWER_SCHEMA["schema"],
                "strict": STRUCTURED_ANSWER_SCHEMA["strict"],
            }
        },
    }
    body = post_responses_request(
        api_key=api_key,
        payload=payload,
    )
    refusal = extract_refusal_text(body)
    if refusal:
        return StructuredModelAnswer(
            status="unknown",
            answer=refusal.strip(),
        )
    return StructuredModelAnswer.from_dict(extract_output_json(body))


def post_responses_request(
    *,
    api_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    req = request.Request(
        RESPONSES_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer {0}".format(api_key),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(read_http_error(exc)) from exc


def extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if output_text:
        return output_text.strip()

    texts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    return "\n".join(texts).strip()


def extract_output_json(payload: dict[str, Any]) -> dict[str, Any]:
    output_text = extract_output_text(payload)
    if not output_text:
        raise RuntimeError("Responses API returned no structured output text.")
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Responses API returned invalid structured JSON: {0}".format(output_text)
        ) from exc


def extract_refusal_text(payload: dict[str, Any]) -> str | None:
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "refusal" and content.get("refusal"):
                return str(content["refusal"]).strip()
    return None


def read_http_error(exc: error.HTTPError) -> str:
    body = exc.read().decode("utf-8", errors="replace")
    url = getattr(exc, "full_url", None) or getattr(exc, "url", None) or exc.geturl()
    return "HTTP {0} from {1}: {2}".format(exc.code, url, body or exc.reason)
