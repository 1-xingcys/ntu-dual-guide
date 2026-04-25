from __future__ import annotations

import hashlib
from typing import Any


class BaseGoldChunker:
    chunker_name = "base_chunker"
    chunker_version = "v1"

    def build_document(self, silver_document: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def scoped_metadata(
        self,
        silver_document: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return build_scope_metadata(silver_document, metadata)

    def processing_fingerprint(self, silver_processing_fingerprint: str) -> str:
        payload = "|".join(
            [
                silver_processing_fingerprint,
                self.chunker_name,
                self.chunker_version,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_scope_metadata(
    silver_document: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    scoped_metadata = dict(metadata)
    content = silver_document.get("content") or {}
    scoped_metadata["year_scope"] = infer_year_scope(
        doc_type=silver_document.get("doc_type"),
        metadata=scoped_metadata,
        content=content,
    )
    scoped_metadata["department_scope"] = infer_department_scope(
        metadata=scoped_metadata,
        content=content,
        source_id=str(silver_document.get("source_id") or ""),
        title=str(silver_document.get("title") or ""),
    )
    return scoped_metadata


def infer_year_scope(*, doc_type: str | None, metadata: dict[str, Any], content: dict[str, Any]) -> str:
    if doc_type in {"curriculum_required_summary", "curriculum_required_courses"}:
        return str(metadata.get("admission_year") or content.get("admission_year") or "all")
    if doc_type == "dual_major_policy":
        return str(metadata.get("academic_year") or content.get("academic_year") or "all")
    return "all"


def infer_department_scope(
    *,
    metadata: dict[str, Any],
    content: dict[str, Any],
    source_id: str,
    title: str,
) -> str:
    explicit_code = metadata.get("department_code") or content.get("department_code")
    if explicit_code:
        return str(explicit_code)

    department_name = str(
        metadata.get("department_name") or content.get("department_name") or title
    )
    inferred = infer_department_code(department_name) or infer_department_code(source_id)
    return inferred or "all"


def infer_department_code(text: str) -> str | None:
    normalized = text.lower()
    if "3030" in normalized or "經濟" in text or "econ" in normalized:
        return "3030"
    if "9020" in normalized or "資訊工程" in text or "資工" in text or "csie" in normalized:
        return "9020"
    return None
