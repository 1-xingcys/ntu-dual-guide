from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


GOLD_SCHEMA_VERSION = "gold.document.v1"


def isoformat_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GoldChunk:
    chunk_id: str
    chunk_type: str
    title: str
    text: str
    order: int
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type,
            "title": self.title,
            "text": self.text,
            "order": self.order,
            "metadata": self.metadata or {},
        }


@dataclass
class GoldDocument:
    source_id: str
    doc_type: str
    title: str
    source_path: str
    source_hash: str
    silver_processing_fingerprint: str
    chunker_name: str
    chunker_version: str
    processing_fingerprint: str
    chunks: list[GoldChunk]
    source_url: Optional[str] = None
    language: str = "zh-TW"
    authority_level: str = "secondary"
    captured_at: Optional[str] = None
    schema_version: str = GOLD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "source_hash": self.source_hash,
            "silver_processing_fingerprint": self.silver_processing_fingerprint,
            "chunker_name": self.chunker_name,
            "chunker_version": self.chunker_version,
            "processing_fingerprint": self.processing_fingerprint,
            "language": self.language,
            "authority_level": self.authority_level,
            "captured_at": self.captured_at or isoformat_utc_now(),
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
