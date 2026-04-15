from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


SILVER_SCHEMA_VERSION = "silver.document.v1"


def isoformat_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FaqQAPair:
    qa_id: str
    question: str
    answer: str
    topics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "qa_id": self.qa_id,
            "question": self.question,
            "answer": self.answer,
            "topics": self.topics,
        }


@dataclass
class FaqContent:
    qa_pairs: list[FaqQAPair]

    def to_dict(self) -> dict[str, Any]:
        return {"qa_pairs": [pair.to_dict() for pair in self.qa_pairs]}


@dataclass
class DualMajorPolicySection:
    section_id: str
    label: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "label": self.label,
            "text": self.text,
        }


@dataclass
class DualMajorPolicyContent:
    academic_year: Optional[str]
    department_name: Optional[str]
    quota: Optional[str]
    contact_phone: Optional[str]
    sections: list[DualMajorPolicySection]

    def to_dict(self) -> dict[str, Any]:
        return {
            "academic_year": self.academic_year,
            "department_name": self.department_name,
            "quota": self.quota,
            "contact_phone": self.contact_phone,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass
class SilverDocument:
    source_id: str
    doc_type: str
    title: str
    source_path: str
    source_hash: str
    parser_name: str
    parser_version: str
    normalizer_version: str
    processing_fingerprint: str
    content: Any
    source_url: Optional[str] = None
    language: str = "zh-TW"
    authority_level: str = "secondary"
    captured_at: Optional[str] = None
    schema_version: str = SILVER_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        captured_at = self.captured_at or isoformat_utc_now()
        content = self.content.to_dict() if hasattr(self.content, "to_dict") else self.content
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "doc_type": self.doc_type,
            "title": self.title,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "source_hash": self.source_hash,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "normalizer_version": self.normalizer_version,
            "processing_fingerprint": self.processing_fingerprint,
            "language": self.language,
            "authority_level": self.authority_level,
            "captured_at": captured_at,
            "content": content,
        }
