from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"
EVALS_SRC = REPO_ROOT / "packages" / "evals" / "src"

for path in [INGESTION_SRC, RAG_SRC, EVALS_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ntu_dual_guide_evals.deepeval_runner import run_deepeval_case
from ntu_dual_guide_evals.deepeval_runner import summarize_deepeval_results
from ntu_dual_guide_evals.deepeval_runner import error_deepeval_case_result
from ntu_dual_guide_evals.golden_bench import load_golden_bench
from ntu_dual_guide_evals.progress import EvalProgress
from ntu_dual_guide_rag.llm_only_service import LlmOnlyService
from ntu_dual_guide_rag.service import RagService
from ntu_dual_guide_rag.settings import RagSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeepEval on the golden bench.")
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
        help="Evaluation mode.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="DeepEval judge model. Defaults to DEEPEVAL_JUDGE_MODEL or gpt-4.1-mini.",
    )
    parser.add_argument(
        "--answer-relevancy-threshold",
        type=float,
        default=0.5,
        help="Threshold for AnswerRelevancyMetric.",
    )
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=0.7,
        help="Threshold for FaithfulnessMetric.",
    )
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="Include unknown/refusal cases in DeepEval instead of skipping them.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the stderr progress bar.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = (REPO_ROOT / args.dataset).resolve()
    cases = load_golden_bench(dataset_path)
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]

    _ = RagSettings.from_env(REPO_ROOT)
    judge_model = args.judge_model or resolve_judge_model()
    service = build_service(args.mode)
    progress = EvalProgress(len(cases), enabled=not args.no_progress)
    results = []
    for index, case in enumerate(cases, start=1):
        progress.start_case(index - 1, case.case_id)
        try:
            result = run_deepeval_case(
                service,
                case,
                mode=args.mode,
                judge_model=judge_model,
                answer_relevancy_threshold=args.answer_relevancy_threshold,
                faithfulness_threshold=args.faithfulness_threshold,
                include_unknown=args.include_unknown,
            )
        except Exception as exc:
            result = error_deepeval_case_result(
                case,
                mode=args.mode,
                error_message=str(exc),
            )
        results.append(result)
        if result.errored:
            state = "error"
        else:
            state = "skip" if result.skipped else "done"
        progress.finish_case(index, case.case_id, state=state)
    progress.close()
    summary = summarize_deepeval_results(
        results,
        mode=args.mode,
        judge_model=judge_model,
    )

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


def resolve_judge_model() -> str:
    return os.environ.get("DEEPEVAL_JUDGE_MODEL", "gpt-4.1-mini")


if __name__ == "__main__":
    main()
