from pathlib import Path
import argparse
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"

for path in [INGESTION_SRC, RAG_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ntu_dual_guide_rag.service import RagService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the backend MVP RAG service from the CLI.")
    parser.add_argument("question", help="Question to ask.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = RagService.from_repo_root(REPO_ROOT)
    result = service.answer(args.question)
    print(result.to_dict())


if __name__ == "__main__":
    main()
