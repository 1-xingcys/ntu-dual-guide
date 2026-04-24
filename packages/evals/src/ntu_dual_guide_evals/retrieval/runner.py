from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Iterable

from ntu_dual_guide_evals.retrieval.bench import RetrievalCase
from ntu_dual_guide_rag.models import RetrievalChunk
from ntu_dual_guide_rag.retriever import Retriever


DEFAULT_K_VALUES: tuple[int, ...] = (1, 3, 5, 10)


@dataclass
class CaseResult:
    case_id: str
    case_type: str
    question: str
    expected_chunk_groups: list[list[str]]
    retrieved_chunk_ids: list[str]
    retrieved_scores: list[float]
    first_hit_rank: int | None  # rank of first chunk in any group
    first_complete_rank: int | None  # rank at which the best group becomes complete
    hit_at_k: dict[int, bool] = field(default_factory=dict)
    group_recall_at_k: dict[int, float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    error: str | None = None


def _group_completion_rank(group: list[str], retrieved_ids: list[str]) -> int | None:
    """Smallest rank at which all chunks in `group` appear in retrieved_ids."""
    needed = set(group)
    if not needed:
        return None
    seen: set[str] = set()
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in needed:
            seen.add(chunk_id)
            if seen == needed:
                return rank
    return None


def evaluate_case(
    case: RetrievalCase,
    retrieved: list[RetrievalChunk],
    k_values: Iterable[int],
) -> CaseResult:
    retrieved_ids = [chunk.chunk_id for chunk in retrieved]
    retrieved_scores = [float(chunk.score) for chunk in retrieved]
    all_expected = case.all_expected_chunk_ids

    first_hit_rank: int | None = None
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in all_expected:
            first_hit_rank = rank
            break

    # Best group completion rank across all groups.
    completion_ranks = [
        _group_completion_rank(group, retrieved_ids)
        for group in case.expected_chunk_groups
    ]
    completion_ranks = [r for r in completion_ranks if r is not None]
    first_complete_rank = min(completion_ranks) if completion_ranks else None

    hit_at_k: dict[int, bool] = {}
    group_recall_at_k: dict[int, float] = {}
    for k in k_values:
        top_k_ids = set(retrieved_ids[:k])
        # hit@k: at least one group fully ⊆ top-k
        hit_at_k[k] = any(
            group and set(group).issubset(top_k_ids)
            for group in case.expected_chunk_groups
        )
        # group_recall@k: best partial-credit across groups
        if case.expected_chunk_groups:
            group_recall_at_k[k] = max(
                (len(set(group) & top_k_ids) / len(group)) if group else 0.0
                for group in case.expected_chunk_groups
            )
        else:
            group_recall_at_k[k] = 0.0

    return CaseResult(
        case_id=case.case_id,
        case_type=case.case_type,
        question=case.question,
        expected_chunk_groups=[list(g) for g in case.expected_chunk_groups],
        retrieved_chunk_ids=retrieved_ids,
        retrieved_scores=retrieved_scores,
        first_hit_rank=first_hit_rank,
        first_complete_rank=first_complete_rank,
        hit_at_k=hit_at_k,
        group_recall_at_k=group_recall_at_k,
        tags=list(case.tags),
    )


def error_case_result(case: RetrievalCase, k_values: Iterable[int], error: str) -> CaseResult:
    return CaseResult(
        case_id=case.case_id,
        case_type=case.case_type,
        question=case.question,
        expected_chunk_groups=[list(g) for g in case.expected_chunk_groups],
        retrieved_chunk_ids=[],
        retrieved_scores=[],
        first_hit_rank=None,
        first_complete_rank=None,
        hit_at_k={k: False for k in k_values},
        group_recall_at_k={k: 0.0 for k in k_values},
        tags=list(case.tags),
        error=error,
    )


def aggregate(results: list[CaseResult], k_values: Iterable[int]) -> dict[str, float]:
    n = len(results)
    if n == 0:
        return {}
    metrics: dict[str, float] = {}
    for k in k_values:
        metrics["hit@{0}".format(k)] = sum(
            1 for r in results if r.hit_at_k.get(k)
        ) / n
        metrics["group_recall@{0}".format(k)] = sum(
            r.group_recall_at_k.get(k, 0.0) for r in results
        ) / n
    # MRR uses first hit rank (any expected chunk).
    rr_sum = sum((1.0 / r.first_hit_rank) for r in results if r.first_hit_rank)
    metrics["mrr"] = rr_sum / n
    # Reciprocal of first-complete-group rank: rewards quickly completing a full group.
    crr_sum = sum((1.0 / r.first_complete_rank) for r in results if r.first_complete_rank)
    metrics["mean_complete_rr"] = crr_sum / n
    error_count = sum(1 for r in results if r.error)
    metrics["error_rate"] = error_count / n
    return metrics


def run_bench(
    retriever: Retriever,
    cases: list[RetrievalCase],
    *,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    progress=None,
) -> tuple[list[CaseResult], dict]:
    results: list[CaseResult] = []
    for index, case in enumerate(cases, start=1):
        if progress is not None:
            progress.start_case(index - 1, case.case_id)
        try:
            retrieved = retriever.retrieve(case.question)
            result = evaluate_case(case, retrieved, k_values)
            state = "hit" if result.hit_at_k.get(max(k_values)) else "miss"
        except Exception as exc:  # noqa: BLE001
            result = error_case_result(case, k_values, error=str(exc))
            state = "error"
        results.append(result)
        if progress is not None:
            progress.finish_case(index, case.case_id, state=state)

    summary = {
        "overall": aggregate(results, k_values),
        "by_type": {},
    }
    case_types = sorted({r.case_type for r in results})
    for case_type in case_types:
        subset = [r for r in results if r.case_type == case_type]
        summary["by_type"][case_type] = {
            "count": len(subset),
            **aggregate(subset, k_values),
        }
    return results, summary


def build_report(
    retriever: Retriever,
    bench_path: Path,
    cases: list[RetrievalCase],
    results: list[CaseResult],
    summary: dict,
    k_values: tuple[int, ...],
) -> dict:
    return {
        "retriever_name": getattr(retriever, "name", retriever.__class__.__name__),
        "bench_path": str(bench_path),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_cases": len(cases),
        "k_values": list(k_values),
        "metrics": summary["overall"],
        "by_type": summary["by_type"],
        "per_case": [_case_result_to_dict(r) for r in results],
    }


def _case_result_to_dict(result: CaseResult) -> dict:
    return {
        "case_id": result.case_id,
        "case_type": result.case_type,
        "question": result.question,
        "expected_chunk_groups": result.expected_chunk_groups,
        "retrieved_chunk_ids": result.retrieved_chunk_ids,
        "retrieved_scores": result.retrieved_scores,
        "first_hit_rank": result.first_hit_rank,
        "first_complete_rank": result.first_complete_rank,
        "hit_at_k": {str(k): v for k, v in result.hit_at_k.items()},
        "group_recall_at_k": {str(k): v for k, v in result.group_recall_at_k.items()},
        "tags": result.tags,
        "error": result.error,
    }
