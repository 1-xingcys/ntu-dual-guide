from __future__ import annotations

import os
from pathlib import Path
import argparse
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.dataset_manifest import resolve_stage_path
from ntu_dual_guide_ingestion.index_records import write_index_records_manifest
from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import require_env
from ntu_dual_guide_ingestion.vector_clients import upsert_vectors_pinecone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed index records and upsert them to Pinecone.")
    parser.add_argument(
        "input_root",
        nargs="?",
        default="artifacts/index-records",
        help="Root directory containing records.jsonl.",
    )
    parser.add_argument(
        "--dataset-version",
        required=True,
        help="Logical dataset snapshot version, for example 2026-04-15.003.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Target vector namespace. Defaults to dataset_version.",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model to use.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=32,
        help="How many records to send to the embeddings API per request.",
    )
    parser.add_argument(
        "--upsert-batch-size",
        type=int,
        default=100,
        help="How many vectors to send to Pinecone per upsert request.",
    )
    parser.add_argument(
        "--manifest-root",
        default="data/manifests",
        help="Manifest output root directory.",
    )
    parser.add_argument(
        "--pinecone-api-version",
        default="2026-04",
        help="Pinecone API version header to send.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate records and write a run manifest without calling external APIs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    namespace = args.namespace or args.dataset_version
    input_root = resolve_stage_path(
        args.input_root,
        "artifacts/index-records",
        REPO_ROOT,
        args.dataset_version,
    )
    records_path = input_root / "records.jsonl"
    manifest_root = (REPO_ROOT / args.manifest_root).resolve()

    records = load_records(records_path)
    assert_record_dataset_version(records, args.dataset_version)
    run_manifest = {
        "schema_version": "index.pinecone_upsert_manifest.v1",
        "dataset_version": args.dataset_version,
        "namespace": namespace,
        "embedding_model": args.embedding_model,
        "pinecone_api_version": args.pinecone_api_version,
        "record_count": len(records),
        "records_path": str(records_path),
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        output_path = manifest_root / args.dataset_version / "pinecone_upsert.json"
        write_index_records_manifest(run_manifest, output_path)
        print(output_path.relative_to(REPO_ROOT))
        return

    openai_api_key = require_env("OPENAI_API_KEY")
    pinecone_api_key = require_env("PINECONE_API_KEY")
    pinecone_index_host = require_env("PINECONE_INDEX_HOST")

    vectors = build_vectors(
        records,
        embedding_model=args.embedding_model,
        embedding_batch_size=args.embedding_batch_size,
        openai_api_key=openai_api_key,
    )
    upserted_count = upsert_vectors(
        vectors,
        namespace=namespace,
        upsert_batch_size=args.upsert_batch_size,
        pinecone_api_key=pinecone_api_key,
        pinecone_index_host=pinecone_index_host,
        pinecone_api_version=args.pinecone_api_version,
    )
    run_manifest["upserted_count"] = upserted_count
    output_path = manifest_root / args.dataset_version / "pinecone_upsert.json"
    write_index_records_manifest(run_manifest, output_path)
    print(output_path.relative_to(REPO_ROOT))


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


def load_records(records_path: Path) -> list[dict]:
    if not records_path.exists():
        raise FileNotFoundError("Index records file not found: {0}".format(records_path))
    records: list[dict] = []
    for line in records_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    if any(record.get("dataset_version") is None for record in records):
        raise ValueError("records.jsonl is missing dataset_version fields")
    return records


def assert_record_dataset_version(records: list[dict], dataset_version: str) -> None:
    mismatches = [record["id"] for record in records if record.get("dataset_version") != dataset_version]
    if mismatches:
        raise ValueError(
            "records.jsonl contains dataset_version mismatches; first record id: {0}".format(
                mismatches[0]
            )
        )


def build_vectors(
    records: list[dict],
    *,
    embedding_model: str,
    embedding_batch_size: int,
    openai_api_key: str,
) -> list[dict]:
    vectors: list[dict] = []
    for start in range(0, len(records), embedding_batch_size):
        batch = records[start : start + embedding_batch_size]
        embeddings = embed_texts_openai(
            [record["text"] for record in batch],
            model=embedding_model,
            api_key=openai_api_key,
        )
        for record, embedding in zip(batch, embeddings):
            vectors.append(
                {
                    "id": record["id"],
                    "values": embedding,
                    "metadata": record["metadata"],
                }
            )
    return vectors


def upsert_vectors(
    vectors: list[dict],
    *,
    namespace: str,
    upsert_batch_size: int,
    pinecone_api_key: str,
    pinecone_index_host: str,
    pinecone_api_version: str,
) -> int:
    total = 0
    for start in range(0, len(vectors), upsert_batch_size):
        batch = vectors[start : start + upsert_batch_size]
        response = upsert_vectors_pinecone(
            batch,
            namespace=namespace,
            index_host=pinecone_index_host,
            api_key=pinecone_api_key,
            api_version=pinecone_api_version,
        )
        total += int(response.get("upsertedCount", 0))
    return total


if __name__ == "__main__":
    main()
