from __future__ import annotations

import json
import os
from typing import Any
from urllib import error
from urllib import request


OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_PINECONE_API_VERSION = "2026-04"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError("Missing required environment variable: {0}".format(name))
    return value


def embed_texts_openai(
    texts: list[str],
    *,
    model: str,
    api_key: str,
) -> list[list[float]]:
    payload = json.dumps(
        {
            "model": model,
            "input": texts,
            "encoding_format": "float",
        }
    ).encode("utf-8")
    req = request.Request(
        OPENAI_EMBEDDINGS_URL,
        data=payload,
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
    return [item["embedding"] for item in body["data"]]


def upsert_vectors_pinecone(
    vectors: list[dict[str, Any]],
    *,
    namespace: str,
    index_host: str,
    api_key: str,
    api_version: str = DEFAULT_PINECONE_API_VERSION,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "vectors": vectors,
            "namespace": namespace,
        }
    ).encode("utf-8")
    req = request.Request(
        normalize_pinecone_upsert_url(index_host),
        data=payload,
        headers={
            "Api-Key": api_key,
            "Content-Type": "application/json",
            "X-Pinecone-Api-Version": api_version,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(read_http_error(exc)) from exc


def normalize_pinecone_upsert_url(index_host: str) -> str:
    if index_host.startswith("https://"):
        return "{0}/vectors/upsert".format(index_host.rstrip("/"))
    if index_host.startswith("http://"):
        return "{0}/vectors/upsert".format(index_host.rstrip("/"))
    return "https://{0}/vectors/upsert".format(index_host.rstrip("/"))


def read_http_error(exc: error.HTTPError) -> str:
    body = exc.read().decode("utf-8", errors="replace")
    url = getattr(exc, "full_url", None) or getattr(exc, "url", None) or exc.geturl()
    return "HTTP {0} from {1}: {2}".format(exc.code, url, body or exc.reason)
