from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class RagSettings:
    openai_api_key: str
    openai_model: str
    openai_embedding_model: str
    pinecone_api_key: str
    pinecone_index_host: str
    pinecone_api_version: str
    dataset_version: str
    namespace: str
    top_k: int
    min_score: float

    @classmethod
    def from_env(cls, repo_root: Path) -> "RagSettings":
        load_dotenv(repo_root / ".env")
        dataset_version = require_env("RAG_DATASET_VERSION")
        namespace = os.environ.get("RAG_NAMESPACE", dataset_version)
        return cls(
            openai_api_key=require_env("OPENAI_API_KEY"),
            openai_model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-mini"),
            openai_embedding_model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            pinecone_api_key=require_env("PINECONE_API_KEY"),
            pinecone_index_host=require_env("PINECONE_INDEX_HOST"),
            pinecone_api_version=os.environ.get("PINECONE_API_VERSION", "2026-04"),
            dataset_version=dataset_version,
            namespace=namespace,
            top_k=int(os.environ.get("RAG_TOP_K", "6")),
            min_score=float(os.environ.get("RAG_MIN_SCORE", "0.55")),
        )


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError("Missing required environment variable: {0}".format(name))
    return value
