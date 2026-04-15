from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.bronze_router import RawToBronzeRouter
from ntu_dual_guide_ingestion.bronze_router import bronze_output_path
from ntu_dual_guide_ingestion.bronze_router import iter_raw_files
from ntu_dual_guide_ingestion.bronze_router import write_bronze_document
from ntu_dual_guide_ingestion.dataset_manifest import resolve_stage_path
from ntu_dual_guide_ingestion.dataset_manifest import write_stage_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform raw files into bronze documents.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="data/raw",
        help="Raw file or directory to transform.",
    )
    parser.add_argument(
        "output_root",
        nargs="?",
        default="data/bronze",
        help="Bronze output root directory.",
    )
    parser.add_argument(
        "--raw-root",
        default="data/raw",
        help="Root directory used to compute routing and mirrored bronze paths.",
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
    raw_root = (REPO_ROOT / args.raw_root).resolve()
    input_path = (REPO_ROOT / args.input_path).resolve()
    output_root = resolve_stage_path(
        args.output_root,
        "data/bronze",
        REPO_ROOT,
        args.dataset_version,
    )
    manifest_root = (REPO_ROOT / args.manifest_root).resolve()

    router = RawToBronzeRouter()
    for raw_path in iter_raw_files(input_path):
        payload = router.build_bronze_document(raw_path, raw_root, args.dataset_version)
        output_path = bronze_output_path(raw_path, raw_root, output_root)
        write_bronze_document(payload, output_path)
        print(output_path.relative_to(REPO_ROOT))
    manifest_path = write_stage_manifest(
        stage_name="raw_to_bronze",
        dataset_version=args.dataset_version,
        output_root=output_root,
        manifest_root=manifest_root,
    )
    print(manifest_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
