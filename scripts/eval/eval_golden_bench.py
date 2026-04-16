from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"
EVALS_SRC = REPO_ROOT / "packages" / "evals" / "src"

for path in [INGESTION_SRC, RAG_SRC, EVALS_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ntu_dual_guide_evals.golden_bench import load_golden_bench
from ntu_dual_guide_evals.runner import run_case
from ntu_dual_guide_evals.runner import summarize_results
from ntu_dual_guide_rag.llm_only_service import LlmOnlyService
from ntu_dual_guide_rag.service import RagService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the golden bench against the backend MVP.")
    parser.add_argument(
        "--dataset",
        default="packages/evals/datasets/golden_bench_v1.jsonl",
        help="Golden bench dataset path.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON report.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Run only one case by case_id.",
    )
    parser.add_argument(
        "--mode",
        choices=["rag", "llm_only"],
        default="rag",
        help="Evaluation mode. 'rag' uses retrieval + generation, 'llm_only' uses the model without retrieval.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = (REPO_ROOT / args.dataset).resolve()
    cases = load_golden_bench(dataset_path)
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]
    service = build_service(args.mode)
    results = [run_case(service, case, mode=args.mode) for case in cases]
    summary = summarize_results(results, mode=args.mode)

    if args.output:
        output_path = (REPO_ROOT / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output_path.relative_to(REPO_ROOT))
        return

    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_service(mode: str):
    if mode == "llm_only":
        return LlmOnlyService.from_repo_root(REPO_ROOT)
    return RagService.from_repo_root(REPO_ROOT)


if __name__ == "__main__":
    main()
