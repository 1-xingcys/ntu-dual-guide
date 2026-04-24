from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_SRC = REPO_ROOT / "packages" / "ingestion" / "src"
RAG_SRC = REPO_ROOT / "packages" / "rag" / "src"
EVALS_SRC = REPO_ROOT / "packages" / "evals" / "src"

for path in [INGESTION_SRC, RAG_SRC, EVALS_SRC]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ntu_dual_guide_evals.retrieval.bench import load_retrieval_bench  # noqa: E402
from ntu_dual_guide_evals.retrieval.runner import build_report  # noqa: E402
from ntu_dual_guide_evals.retrieval.runner import run_bench  # noqa: E402
from ntu_dual_guide_evals.utils.progress import EvalProgress  # noqa: E402
from ntu_dual_guide_rag.retriever import PineconeRetriever  # noqa: E402
from ntu_dual_guide_rag.retriever import Retriever  # noqa: E402
from ntu_dual_guide_rag.settings import RagSettings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the retrieval bench against a configurable retriever."
    )
    parser.add_argument(
        "--dataset",
        default="packages/evals/datasets/retrieval_bench_v1.jsonl",
        help="Retrieval bench dataset path (JSONL).",
    )
    parser.add_argument(
        "--retriever",
        choices=["dense"],
        default="dense",
        help="Which retriever variant to evaluate. Add new ones in build_retriever().",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="How many candidates the retriever should fetch per query.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Override min_score; default 0.0 to avoid biasing recall metrics.",
    )
    parser.add_argument(
        "--k-values",
        default="1,3,5,10",
        help="Comma-separated k values used to compute Hit@k / Recall@k.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Run only one case by case_id.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON report (relative to repo root).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the stderr progress bar.",
    )
    return parser.parse_args()


def build_retriever(name: str, *, top_k: int, min_score: float) -> Retriever:
    if name == "dense":
        settings = RagSettings.from_env(REPO_ROOT)
        settings.top_k = top_k
        settings.min_score = min_score
        return PineconeRetriever(
            settings,
            name="dense-pinecone-top{0}".format(top_k),
        )
    raise ValueError("Unknown retriever: {0}".format(name))


def main() -> None:
    args = parse_args()
    bench_path = (REPO_ROOT / args.dataset).resolve()
    cases = load_retrieval_bench(bench_path)
    if args.case_id:
        cases = [c for c in cases if c.case_id == args.case_id]
    if not cases:
        raise SystemExit("No cases to run.")

    k_values = tuple(int(s) for s in args.k_values.split(",") if s.strip())
    if not k_values:
        raise SystemExit("--k-values must contain at least one integer.")

    retriever = build_retriever(
        args.retriever,
        top_k=max(args.top_k, max(k_values)),
        min_score=args.min_score,
    )

    progress = EvalProgress(len(cases), enabled=not args.no_progress)
    results, summary = run_bench(retriever, cases, k_values=k_values, progress=progress)
    progress.close()

    report = build_report(retriever, bench_path, cases, results, summary, k_values)

    if args.output:
        output_path = (REPO_ROOT / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(output_path.relative_to(REPO_ROOT))
        return

    print(
        json.dumps(
            {
                "retriever_name": report["retriever_name"],
                "total_cases": report["total_cases"],
                "metrics": report["metrics"],
                "by_type": report["by_type"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
