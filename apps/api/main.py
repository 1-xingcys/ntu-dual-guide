from __future__ import annotations

import json
from pathlib import Path
import sys
from functools import lru_cache
from typing import Iterator

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"

for path in [INGESTION_SRC, RAG_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ntu_dual_guide_rag.models import ChatAnswer, RetrievalChunk
from ntu_dual_guide_rag.service import RagService


app = FastAPI(title="NTU Dual Guide API", version="0.1.0")


class ChatRequest(BaseModel):
    message: str


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    return RagService.from_repo_root(REPO_ROOT)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat")
def chat(request: ChatRequest) -> dict:
    try:
        result = get_rag_service().answer(request.message)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result.to_dict()


@app.post("/v1/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        sse_event_stream(request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def sse_event_stream(question: str) -> Iterator[bytes]:
    service = get_rag_service()
    try:
        for kind, payload in service.stream_answer(question):
            yield encode_sse(kind, sse_payload(kind, payload))
    except (ValueError, RuntimeError) as exc:
        yield encode_sse("error", {"message": str(exc)})
        return
    yield encode_sse("done", {})


def sse_payload(kind: str, payload: object) -> object:
    if kind == "retrieved":
        chunks = payload if isinstance(payload, list) else []
        return {
            "count": len(chunks),
            "chunks": [retrieval_chunk_summary(chunk) for chunk in chunks],
        }
    if kind == "stage":
        return {"stage": payload}
    if kind == "token":
        return {"delta": payload}
    if kind == "reasoning":
        return {"delta": payload}
    if kind == "final":
        if isinstance(payload, ChatAnswer):
            return payload.to_dict()
        return payload
    return {"value": payload}


def retrieval_chunk_summary(chunk: RetrievalChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "score": chunk.score,
        "title": chunk.title,
        "source_id": chunk.source_id,
    }


def encode_sse(event: str, data: object) -> bytes:
    body = json.dumps(data, ensure_ascii=False)
    return "event: {0}\ndata: {1}\n\n".format(event, body).encode("utf-8")
