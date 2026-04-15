from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


BRONZE_SCHEMA_VERSION = "bronze.document.v1"


def isoformat_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BronzeBlock:
    block_id: str
    block_type: str
    text: str
    order: int
    attributes: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_type": self.block_type,
            "text": self.text,
            "order": self.order,
            "attributes": self.attributes or {},
        }


@dataclass
class BronzeContent:
    title: Optional[str]
    blocks: list[BronzeBlock]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "blocks": [block.to_dict() for block in self.blocks],
        }


@dataclass
class BronzeDocument:
    raw_path: str
    file_name: str
    file_format: str
    family: str
    category: Optional[str]
    parser_name: str
    parser_version: str
    parser_profile: str
    source_hash: str
    processing_fingerprint: str
    content: BronzeContent
    source_url: Optional[str] = None
    captured_at: Optional[str] = None
    schema_version: str = BRONZE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "raw_path": self.raw_path,
            "file_name": self.file_name,
            "file_format": self.file_format,
            "family": self.family,
            "category": self.category,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "parser_profile": self.parser_profile,
            "source_url": self.source_url,
            "source_hash": self.source_hash,
            "processing_fingerprint": self.processing_fingerprint,
            "captured_at": self.captured_at or isoformat_utc_now(),
            "content": self.content.to_dict(),
        }
