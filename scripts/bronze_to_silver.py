from pathlib import Path
import argparse
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.silver_router import BronzeToSilverRouter
from ntu_dual_guide_ingestion.silver_router import iter_bronze_files
from ntu_dual_guide_ingestion.silver_router import silver_output_path
from ntu_dual_guide_ingestion.silver_router import write_silver_document
from ntu_dual_guide_ingestion.dataset_manifest import assert_dataset_version
from ntu_dual_guide_ingestion.dataset_manifest import resolve_stage_path
from ntu_dual_guide_ingestion.dataset_manifest import write_stage_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform bronze documents into silver documents.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="data/bronze",
        help="Bronze file or directory to normalize.",
    )
    parser.add_argument(
        "output_root",
        nargs="?",
        default="data/silver",
        help="Silver output root directory.",
    )
    parser.add_argument(
        "--bronze-root",
        default="data/bronze",
        help="Root directory used to compute mirrored silver paths.",
    )
    parser.add_argument(
        "--dataset-version",
        required=True,
        help="Logical dataset snapshot version, for example 2026-04-15.001.",
    )
    parser.add_argument(
        "--manifest-root",
        default="data/manifests",
        help="Manifest output root directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bronze_root = resolve_stage_path(
        args.bronze_root,
        "data/bronze",
        REPO_ROOT,
        args.dataset_version,
    )
    input_path = resolve_stage_path(
        args.input_path,
        "data/bronze",
        REPO_ROOT,
        args.dataset_version,
    )
    output_root = resolve_stage_path(
        args.output_root,
        "data/silver",
        REPO_ROOT,
        args.dataset_version,
    )
    manifest_root = (REPO_ROOT / args.manifest_root).resolve()

    router = BronzeToSilverRouter()
    for bronze_path in iter_bronze_files(input_path):
        bronze_document = json.loads(bronze_path.read_text(encoding="utf-8"))
        assert_dataset_version(bronze_document, args.dataset_version, bronze_path)
        payload = router.build_silver_document(bronze_path)
        output_path = silver_output_path(bronze_path, bronze_root, output_root)
        write_silver_document(payload, output_path)
        print(output_path.relative_to(REPO_ROOT))
    manifest_path = write_stage_manifest(
        stage_name="bronze_to_silver",
        dataset_version=args.dataset_version,
        output_root=output_root,
        manifest_root=manifest_root,
    )
    print(manifest_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
