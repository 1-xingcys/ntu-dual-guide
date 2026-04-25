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

from ntu_dual_guide_evals.deepeval.runner import error_deepeval_case_result
from ntu_dual_guide_evals.deepeval.runner import run_deepeval_case
from ntu_dual_guide_evals.deepeval.runner import summarize_deepeval_results
from ntu_dual_guide_evals.deterministic.golden_bench import load_golden_bench
from ntu_dual_guide_evals.utils.progress import EvalProgress
from ntu_dual_guide_rag.llm_only_service import LlmOnlyService
from ntu_dual_guide_rag.retrievers import RETRIEVER_CHOICES
from ntu_dual_guide_rag.retrievers import build_retriever
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
        "--retriever",
        choices=RETRIEVER_CHOICES,
        default="dense",
        help="Retriever used in rag mode.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override RAG_TOP_K for this run.",
    )
    parser.add_argument(
        "--dense-top-k",
        type=int,
        default=None,
        help="Dense candidate pool size for hybrid retrieval.",
    )
    parser.add_argument(
        "--sparse-top-k",
        type=int,
        default=None,
        help="BM25 candidate pool size for hybrid retrieval.",
    )
    parser.add_argument(
        "--dense-weight",
        type=float,
        default=1.0,
        help="Weighted RRF contribution for dense ranks in hybrid mode.",
    )
    parser.add_argument(
        "--sparse-weight",
        type=float,
        default=1.0,
        help="Weighted RRF contribution for BM25 ranks in hybrid mode.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF damping constant used in hybrid mode.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Override RAG_MIN_SCORE for this run.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="DeepEval judge model. Defaults to DEEPEVAL_JUDGE_MODEL or gpt-4.1-mini.",
    )
    parser.add_argument(
        "--answer-quality-threshold",
        type=float,
        default=0.5,
        help="Threshold for the generation answer-quality GEval metric.",
    )
    parser.add_argument(
        "--faithfulness-threshold",
        type=float,
        default=0.7,
        help="Threshold for FaithfulnessMetric.",
    )
    parser.add_argument(
        "--hallucination-threshold",
        type=float,
        default=0.5,
        help="Maximum allowed hallucination score for HallucinationMetric.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the stderr progress bar.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_args(args)
    dataset_path = (REPO_ROOT / args.dataset).resolve()
    cases = load_golden_bench(dataset_path)
    if args.case_id:
        cases = [case for case in cases if case.case_id == args.case_id]

    judge_model = args.judge_model or resolve_judge_model()
    service = build_service(args)
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
                answer_quality_threshold=args.answer_quality_threshold,
                faithfulness_threshold=args.faithfulness_threshold,
                hallucination_threshold=args.hallucination_threshold,
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
            state = "done"
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


def build_service(args: argparse.Namespace):
    if args.mode == "llm_only":
        return LlmOnlyService.from_repo_root(REPO_ROOT)
    settings = RagSettings.from_env(REPO_ROOT)
    retriever = build_retriever(
        args.retriever,
        settings=settings,
        repo_root=REPO_ROOT,
        top_k=args.top_k,
        min_score=args.min_score,
        dense_top_k=args.dense_top_k,
        sparse_top_k=args.sparse_top_k,
        dense_weight=args.dense_weight,
        sparse_weight=args.sparse_weight,
        rrf_k=args.rrf_k,
    )
    return RagService(
        settings,
        retriever=retriever,
        generate_on_empty_retrieval=True,
    )


def validate_args(args: argparse.Namespace) -> None:
    if args.mode == "llm_only" and args.retriever != "dense":
        raise SystemExit("--retriever can only be used with --mode rag.")
    if args.top_k is not None and args.top_k <= 0:
        raise SystemExit("--top-k must be positive when set.")
    if args.dense_top_k is not None and args.dense_top_k <= 0:
        raise SystemExit("--dense-top-k must be positive when set.")
    if args.sparse_top_k is not None and args.sparse_top_k <= 0:
        raise SystemExit("--sparse-top-k must be positive when set.")
    if args.dense_weight < 0 or args.sparse_weight < 0:
        raise SystemExit("--dense-weight and --sparse-weight must be non-negative.")
    if args.rrf_k < 0:
        raise SystemExit("--rrf-k must be non-negative.")


def resolve_judge_model() -> str:
    return os.environ.get("DEEPEVAL_JUDGE_MODEL", "gpt-4.1-mini")


if __name__ == "__main__":
    main()
