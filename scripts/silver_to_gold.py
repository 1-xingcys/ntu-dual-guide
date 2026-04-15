from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.gold_router import SilverToGoldRouter
from ntu_dual_guide_ingestion.gold_router import gold_output_path
from ntu_dual_guide_ingestion.gold_router import iter_silver_files
from ntu_dual_guide_ingestion.gold_router import write_gold_document


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    silver_root = (REPO_ROOT / args.silver_root).resolve()
    input_path = (REPO_ROOT / args.input_path).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()

    router = SilverToGoldRouter()
    for silver_path in iter_silver_files(input_path):
        payload = router.build_gold_document(silver_path)
        output_path = gold_output_path(silver_path, silver_root, output_root)
        write_gold_document(payload, output_path)
        print(output_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
