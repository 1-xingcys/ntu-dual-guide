from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ntu_dual_guide_ingestion.dataset_manifest import assert_dataset_version


INDEX_RECORDS_MANIFEST_SCHEMA_VERSION = "index.records_manifest.v1"
DEFAULT_EXCLUDED_SOURCE_IDS = {"csie-handbook-112"}
DEFAULT_EXCLUDED_DOC_TYPES = {"handbook"}


def isoformat_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iter_gold_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*.json")):
        if path.is_file():
            yield path


def parse_csv_set(value: Optional[str]) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def should_include_document(
    gold_document: dict[str, Any],
    include_source_ids: set[str],
    exclude_source_ids: set[str],
    include_doc_types: set[str],
    exclude_doc_types: set[str],
) -> bool:
    source_id = gold_document.get("source_id")
    doc_type = gold_document.get("doc_type")

    if include_source_ids and source_id not in include_source_ids:
        return False
    if include_doc_types and doc_type not in include_doc_types:
        return False
    if source_id in exclude_source_ids:
        return False
    if doc_type in exclude_doc_types:
        return False
    return True


def build_index_records(
    *,
    gold_root: Path,
    dataset_version: str,
    include_source_ids: set[str],
    exclude_source_ids: set[str],
    include_doc_types: set[str],
    exclude_doc_types: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    included_documents: list[dict[str, Any]] = []

    for gold_path in iter_gold_files(gold_root):
        gold_document = json.loads(gold_path.read_text(encoding="utf-8"))
        assert_dataset_version(gold_document, dataset_version, gold_path)
        if not should_include_document(
            gold_document,
            include_source_ids,
            exclude_source_ids,
            include_doc_types,
            exclude_doc_types,
        ):
            continue

        included_documents.append(
            {
                "relative_gold_path": str(gold_path.relative_to(gold_root)),
                "source_id": gold_document["source_id"],
                "doc_type": gold_document["doc_type"],
                "title": gold_document["title"],
                "chunk_count": len(gold_document.get("chunks", [])),
                "processing_fingerprint": gold_document["processing_fingerprint"],
            }
        )
        for chunk in gold_document.get("chunks", []):
            records.append(build_index_record(gold_document, chunk))

    return records, included_documents


def build_index_record(gold_document: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "dataset_version": gold_document["dataset_version"],
        "source_id": gold_document["source_id"],
        "doc_type": gold_document["doc_type"],
        "title": gold_document["title"],
        "authority_level": gold_document.get("authority_level", "secondary"),
        "language": gold_document.get("language", "zh-TW"),
        "source_path": gold_document["source_path"],
        "source_url": gold_document.get("source_url"),
        "source_hash": gold_document["source_hash"],
        "gold_processing_fingerprint": gold_document["processing_fingerprint"],
        "silver_processing_fingerprint": gold_document["silver_processing_fingerprint"],
        "chunk_type": chunk["chunk_type"],
        "chunk_title": chunk["title"],
        "chunk_order": chunk["order"],
        "chunk_text": chunk["text"],
    }
    metadata.update(chunk.get("metadata", {}))
    metadata = sanitize_metadata(metadata)
    return {
        "id": chunk["chunk_id"],
        "dataset_version": gold_document["dataset_version"],
        "text": chunk["text"],
        "metadata": metadata,
    }


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, list):
            cleaned_list = [item for item in value if item is not None]
            if cleaned_list:
                cleaned[key] = cleaned_list
            continue
        cleaned[key] = value
    return cleaned


def build_index_records_manifest(
    *,
    dataset_version: str,
    namespace: str,
    embedding_model: str,
    records: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    include_source_ids: set[str],
    exclude_source_ids: set[str],
    include_doc_types: set[str],
    exclude_doc_types: set[str],
) -> dict[str, Any]:
    fingerprint_payload = "|".join(
        sorted(
            "{0}:{1}".format(record["id"], record["metadata"]["gold_processing_fingerprint"])
            for record in records
        )
    )
    return {
        "schema_version": INDEX_RECORDS_MANIFEST_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "namespace": namespace,
        "embedding_model": embedding_model,
        "created_at": isoformat_utc_now(),
        "document_count": len(documents),
        "record_count": len(records),
        "record_fingerprint": hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
        "include_source_ids": sorted(include_source_ids),
        "exclude_source_ids": sorted(exclude_source_ids),
        "include_doc_types": sorted(include_doc_types),
        "exclude_doc_types": sorted(exclude_doc_types),
        "documents": documents,
    }


def write_records_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    output_path.write_text(payload, encoding="utf-8")


def write_index_records_manifest(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
