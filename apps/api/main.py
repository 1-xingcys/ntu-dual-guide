from __future__ import annotations

from pathlib import Path
import sys
from functools import lru_cache

from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"

for path in [INGESTION_SRC, RAG_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

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
