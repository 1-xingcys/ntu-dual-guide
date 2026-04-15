from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "packages" / "ingestion" / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ntu_dual_guide_ingestion.silver_router import BronzeToSilverRouter
from ntu_dual_guide_ingestion.silver_router import iter_bronze_files
from ntu_dual_guide_ingestion.silver_router import silver_output_path
from ntu_dual_guide_ingestion.silver_router import write_silver_document


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bronze_root = (REPO_ROOT / args.bronze_root).resolve()
    input_path = (REPO_ROOT / args.input_path).resolve()
    output_root = (REPO_ROOT / args.output_root).resolve()

    router = BronzeToSilverRouter()
    for bronze_path in iter_bronze_files(input_path):
        payload = router.build_silver_document(bronze_path)
        output_path = silver_output_path(bronze_path, bronze_root, output_root)
        write_silver_document(payload, output_path)
        print(output_path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
