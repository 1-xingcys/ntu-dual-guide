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
from ntu_dual_guide_rag.retriever import HybridRetriever  # noqa: E402
from ntu_dual_guide_rag.retriever import PineconeRetriever  # noqa: E402
from ntu_dual_guide_rag.retriever import PromotedRetriever  # noqa: E402
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
        choices=["dense", "hybrid", "hybrid_promoted"],
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
        "--dense-top-k",
        type=int,
        default=None,
        help="Dense candidate pool size for hybrid retrieval. Defaults to --top-k.",
    )
    parser.add_argument(
        "--sparse-top-k",
        type=int,
        default=None,
        help="BM25 candidate pool size for hybrid retrieval. Defaults to --top-k.",
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


def build_retriever(
    name: str,
    *,
    top_k: int,
    min_score: float,
    dense_top_k: int | None = None,
    sparse_top_k: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    rrf_k: int = 60,
) -> Retriever:
    settings = RagSettings.from_env(REPO_ROOT)
    settings.top_k = top_k
    settings.min_score = min_score
    if name == "dense":
        return PineconeRetriever(
            settings,
            name="dense-pinecone-top{0}".format(top_k),
        )
    if name == "hybrid":
        final_dense_top_k = max(dense_top_k or top_k, top_k)
        final_sparse_top_k = max(sparse_top_k or top_k, top_k)
        return HybridRetriever(
            settings,
            repo_root=REPO_ROOT,
            dense_top_k=final_dense_top_k,
            sparse_top_k=final_sparse_top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            name=(
                "hybrid-rrf-dense{0}-sparse{1}-dw{2:g}-sw{3:g}-k{4}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
    if name == "hybrid_promoted":
        final_dense_top_k = max(dense_top_k or top_k, top_k)
        final_sparse_top_k = max(sparse_top_k or top_k, top_k)
        candidate_top_k = max(final_dense_top_k, final_sparse_top_k, top_k)
        candidate_settings = RagSettings(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_embedding_model=settings.openai_embedding_model,
            pinecone_api_key=settings.pinecone_api_key,
            pinecone_index_host=settings.pinecone_index_host,
            pinecone_api_version=settings.pinecone_api_version,
            dataset_version=settings.dataset_version,
            namespace=settings.namespace,
            top_k=candidate_top_k,
            min_score=settings.min_score,
        )
        base_retriever = HybridRetriever(
            candidate_settings,
            repo_root=REPO_ROOT,
            dense_top_k=final_dense_top_k,
            sparse_top_k=final_sparse_top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            name=(
                "hybrid-rrf-dense{0}-sparse{1}-candidate{2}-dw{3:g}-sw{4:g}-k{5}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    candidate_top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
        return PromotedRetriever(
            base_retriever,
            repo_root=REPO_ROOT,
            dataset_version=settings.dataset_version,
            top_k=top_k,
            name=(
                "hybrid-promoted-dense{0}-sparse{1}-candidate{2}-final{3}-dw{4:g}-sw{5:g}-k{6}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    candidate_top_k,
                    top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
    raise ValueError("Unknown retriever: {0}".format(name))


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be positive.")
    if args.dense_top_k is not None and args.dense_top_k <= 0:
        raise SystemExit("--dense-top-k must be positive when set.")
    if args.sparse_top_k is not None and args.sparse_top_k <= 0:
        raise SystemExit("--sparse-top-k must be positive when set.")
    if args.dense_weight < 0 or args.sparse_weight < 0:
        raise SystemExit("--dense-weight and --sparse-weight must be non-negative.")
    if args.rrf_k < 0:
        raise SystemExit("--rrf-k must be non-negative.")

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
        dense_top_k=args.dense_top_k,
        sparse_top_k=args.sparse_top_k,
        dense_weight=args.dense_weight,
        sparse_weight=args.sparse_weight,
        rrf_k=args.rrf_k,
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
