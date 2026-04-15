from __future__ import annotations

import json
from typing import Any
from urllib import error
from urllib import request


RESPONSES_API_URL = "https://api.openai.com/v1/responses"


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
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(read_http_error(exc)) from exc
    return extract_output_text(body)


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


def read_http_error(exc: error.HTTPError) -> str:
    body = exc.read().decode("utf-8", errors="replace")
    url = getattr(exc, "full_url", None) or getattr(exc, "url", None) or exc.geturl()
    return "HTTP {0} from {1}: {2}".format(exc.code, url, body or exc.reason)
