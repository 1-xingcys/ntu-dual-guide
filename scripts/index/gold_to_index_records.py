from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.dataset_manifest import resolve_stage_path
from ntu_dual_guide_ingestion.index_records import DEFAULT_EXCLUDED_DOC_TYPES
from ntu_dual_guide_ingestion.index_records import DEFAULT_EXCLUDED_SOURCE_IDS
from ntu_dual_guide_ingestion.index_records import build_index_records
from ntu_dual_guide_ingestion.index_records import build_index_records_manifest
from ntu_dual_guide_ingestion.index_records import parse_csv_set
from ntu_dual_guide_ingestion.index_records import write_index_records_manifest
from ntu_dual_guide_ingestion.index_records import write_records_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flatten gold documents into index-ready records.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="data/gold",
        help="Gold file or directory to flatten.",
    )
    parser.add_argument(
        "output_root",
        nargs="?",
        default="artifacts/index-records",
        help="Output root directory for index records.",
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
        help="Embedding model identifier recorded in the manifest.",
    )
    parser.add_argument(
        "--manifest-root",
        default="data/manifests",
        help="Manifest output root directory.",
    )
    parser.add_argument(
        "--include-source-ids",
        default=None,
        help="Comma-separated allowlist of source_id values.",
    )
    parser.add_argument(
        "--exclude-source-ids",
        default=None,
        help="Comma-separated denylist of source_id values.",
    )
    parser.add_argument(
        "--include-doc-types",
        default=None,
        help="Comma-separated allowlist of doc_type values.",
    )
    parser.add_argument(
        "--exclude-doc-types",
        default=None,
        help="Comma-separated denylist of doc_type values.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    namespace = args.namespace or args.dataset_version
    gold_root = resolve_stage_path(args.input_path, "data/gold", REPO_ROOT, args.dataset_version)
    output_root = resolve_stage_path(
        args.output_root,
        "artifacts/index-records",
        REPO_ROOT,
        args.dataset_version,
    )
    manifest_root = (REPO_ROOT / args.manifest_root).resolve()

    include_source_ids = parse_csv_set(args.include_source_ids)
    exclude_source_ids = DEFAULT_EXCLUDED_SOURCE_IDS | parse_csv_set(args.exclude_source_ids)
    include_doc_types = parse_csv_set(args.include_doc_types)
    exclude_doc_types = DEFAULT_EXCLUDED_DOC_TYPES | parse_csv_set(args.exclude_doc_types)

    records, documents = build_index_records(
        gold_root=gold_root,
        dataset_version=args.dataset_version,
        include_source_ids=include_source_ids,
        exclude_source_ids=exclude_source_ids,
        include_doc_types=include_doc_types,
        exclude_doc_types=exclude_doc_types,
    )

    records_path = output_root / "records.jsonl"
    write_records_jsonl(records, records_path)
    manifest = build_index_records_manifest(
        dataset_version=args.dataset_version,
        namespace=namespace,
        embedding_model=args.embedding_model,
        records=records,
        documents=documents,
        include_source_ids=include_source_ids,
        exclude_source_ids=exclude_source_ids,
        include_doc_types=include_doc_types,
        exclude_doc_types=exclude_doc_types,
    )
    manifest_path = manifest_root / args.dataset_version / "gold_to_index_records.json"
    write_index_records_manifest(manifest, manifest_path)

    print(records_path.relative_to(REPO_ROOT))
    print(manifest_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
