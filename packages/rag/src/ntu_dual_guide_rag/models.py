from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievalChunk:
    chunk_id: str
    score: float
    source_id: str
    doc_type: str
    chunk_type: str
    title: str
    text: str
    metadata: dict[str, Any]


@dataclass
class Citation:
    index: int
    chunk_id: str
    source_id: str
    title: str
    chunk_title: str
    source_path: str | None
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "title": self.title,
            "chunk_title": self.chunk_title,
            "source_path": self.source_path,
            "score": self.score,
        }


@dataclass
class ChatAnswer:
    answer: str
    status: str
    model: str
    dataset_version: str
    namespace: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievalChunk]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "status": self.status,
            "model": self.model,
            "dataset_version": self.dataset_version,
            "namespace": self.namespace,
            "citations": [citation.to_dict() for citation in self.citations],
            "retrieved_chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "score": chunk.score,
                    "source_id": chunk.source_id,
                    "doc_type": chunk.doc_type,
                    "chunk_type": chunk.chunk_type,
                    "title": chunk.title,
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                }
                for chunk in self.retrieved_chunks
            ],
        }


@dataclass
class StructuredModelAnswer:
    status: str
    answer: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StructuredModelAnswer":
        status = str(payload.get("status", "")).strip()
        answer = str(payload.get("answer", "")).strip()
        if status not in {"answered", "unknown"}:
            raise ValueError("Unsupported structured answer status: {0}".format(status))
        if not answer:
            answer = "不知道" if status == "unknown" else ""
        return cls(
            status=status,
            answer=answer,
        )
