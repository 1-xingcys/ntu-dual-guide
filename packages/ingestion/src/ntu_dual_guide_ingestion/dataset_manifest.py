from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_MANIFEST_SCHEMA_VERSION = "dataset.stage_manifest.v1"


def isoformat_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_stage_path(
    path_arg: str,
    default_arg: str,
    repo_root: Path,
    dataset_version: str,
) -> Path:
    path = (repo_root / path_arg).resolve()
    if path_arg != default_arg:
        return path
    return path / dataset_version


def assert_dataset_version(document: dict[str, Any], dataset_version: str, document_path: Path) -> None:
    actual = document.get("dataset_version")
    if actual != dataset_version:
        raise ValueError(
            "Dataset version mismatch for {0}: expected {1}, got {2}".format(
                document_path, dataset_version, actual
            )
        )


def manifest_output_path(manifest_root: Path, dataset_version: str, stage_name: str) -> Path:
    return manifest_root / dataset_version / "{0}.json".format(stage_name)


def write_stage_manifest(
    *,
    stage_name: str,
    dataset_version: str,
    output_root: Path,
    manifest_root: Path,
) -> Path:
    output_root = output_root.resolve()
    entries: list[dict[str, Any]] = []
    fingerprints: list[str] = []

    for document_path in sorted(output_root.rglob("*.json")):
        document = json.loads(document_path.read_text(encoding="utf-8"))
        assert_dataset_version(document, dataset_version, document_path)
        processing_fingerprint = document.get("processing_fingerprint")
        if processing_fingerprint:
            fingerprints.append(processing_fingerprint)
        entries.append(
            {
                "relative_output_path": str(document_path.relative_to(output_root)),
                "source_id": document.get("source_id"),
                "doc_type": document.get("doc_type"),
                "raw_path": document.get("raw_path"),
                "source_path": document.get("source_path"),
                "source_hash": document.get("source_hash"),
                "processing_fingerprint": processing_fingerprint,
            }
        )

    payload = {
        "schema_version": STAGE_MANIFEST_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "stage": stage_name,
        "created_at": isoformat_utc_now(),
        "document_count": len(entries),
        "dataset_fingerprint": build_dataset_fingerprint(fingerprints),
        "output_root": str(output_root),
        "documents": entries,
    }
    output_path = manifest_output_path(manifest_root, dataset_version, stage_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_dataset_fingerprint(fingerprints: list[str]) -> str:
    payload = "|".join(sorted(set(fingerprints)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
