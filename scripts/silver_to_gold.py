from pathlib import Path
import argparse
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.gold_router import SilverToGoldRouter
from ntu_dual_guide_ingestion.gold_router import gold_output_path
from ntu_dual_guide_ingestion.gold_router import iter_silver_files
from ntu_dual_guide_ingestion.gold_router import write_gold_document
from ntu_dual_guide_ingestion.dataset_manifest import assert_dataset_version
from ntu_dual_guide_ingestion.dataset_manifest import resolve_stage_path
from ntu_dual_guide_ingestion.dataset_manifest import write_stage_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform silver documents into gold chunk documents.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="data/silver",
        help="Silver file or directory to chunk.",
    )
    parser.add_argument(
        "output_root",
        nargs="?",
        default="data/gold",
        help="Gold output root directory.",
    )
    parser.add_argument(
        "--silver-root",
        default="data/silver",
        help="Root directory used to compute mirrored gold paths.",
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
    silver_root = resolve_stage_path(
        args.silver_root,
        "data/silver",
        REPO_ROOT,
        args.dataset_version,
    )
    input_path = resolve_stage_path(
        args.input_path,
        "data/silver",
        REPO_ROOT,
        args.dataset_version,
    )
    output_root = resolve_stage_path(
        args.output_root,
        "data/gold",
        REPO_ROOT,
        args.dataset_version,
    )
    manifest_root = (REPO_ROOT / args.manifest_root).resolve()

    router = SilverToGoldRouter()
    for silver_path in iter_silver_files(input_path):
        silver_document = json.loads(silver_path.read_text(encoding="utf-8"))
        assert_dataset_version(silver_document, args.dataset_version, silver_path)
        payload = router.build_gold_document(silver_path)
        output_path = gold_output_path(silver_path, silver_root, output_root)
        write_gold_document(payload, output_path)
        print(output_path.relative_to(REPO_ROOT))
    manifest_path = write_stage_manifest(
        stage_name="silver_to_gold",
        dataset_version=args.dataset_version,
        output_root=output_root,
        manifest_root=manifest_root,
    )
    print(manifest_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
