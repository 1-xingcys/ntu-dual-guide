from __future__ import annotations

import json
import os
import socket
import time
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

RETRYABLE_HTTP_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


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
    timeout_seconds = get_responses_timeout_seconds()
    max_retries = get_responses_max_retries()
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
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
            with request.urlopen(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if attempt < max_retries and exc.code in RETRYABLE_HTTP_STATUS_CODES:
                sleep_before_retry(attempt)
                last_error = exc
                continue
            raise RuntimeError(read_http_error(exc)) from exc
        except (TimeoutError, socket.timeout, error.URLError) as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_before_retry(attempt)
                continue
            raise RuntimeError(
                "Responses API request failed after {0} attempts: {1}".format(
                    max_retries + 1,
                    exc,
                )
            ) from exc

    raise RuntimeError(
        "Responses API request failed after {0} attempts: {1}".format(
            max_retries + 1,
            last_error or "unknown error",
        )
    )


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


def get_responses_timeout_seconds() -> float:
    return float(os.environ.get("OPENAI_RESPONSES_TIMEOUT_SECONDS", "120"))


def get_responses_max_retries() -> int:
    return int(os.environ.get("OPENAI_RESPONSES_MAX_RETRIES", "2"))


def sleep_before_retry(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 8))
