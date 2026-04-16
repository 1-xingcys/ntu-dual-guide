from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Protocol

from ntu_dual_guide_evals.golden_bench import GoldenBenchCase
from ntu_dual_guide_rag.models import ChatAnswer


class AnsweringService(Protocol):
    def answer(self, question: str) -> ChatAnswer:
        ...


@dataclass
class DeepEvalMetricResult:
    name: str
    score: float | None
    success: bool | None
    threshold: float | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "success": self.success,
            "threshold": self.threshold,
            "reason": self.reason,
        }


@dataclass
class DeepEvalCaseResult:
    mode: str
    case_id: str
    skipped: bool
    skip_reason: str | None
    answer: str
    status: str
    metrics: list[DeepEvalMetricResult]
    retrieved_chunk_ids: list[str]
    retrieved_source_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "case_id": self.case_id,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "answer": self.answer,
            "status": self.status,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "retrieved_source_ids": self.retrieved_source_ids,
        }


def run_deepeval_case(
    service: AnsweringService,
    case: GoldenBenchCase,
    *,
    mode: str,
    judge_model: str,
    answer_relevancy_threshold: float,
    faithfulness_threshold: float,
    include_unknown: bool,
) -> DeepEvalCaseResult:
    result = service.answer(case.question)

    if result.status == "unknown" and not include_unknown:
        return DeepEvalCaseResult(
            mode=mode,
            case_id=case.case_id,
            skipped=True,
            skip_reason="unknown_case_skipped",
            answer=result.answer,
            status=result.status,
            metrics=[],
            retrieved_chunk_ids=[chunk.chunk_id for chunk in result.retrieved_chunks],
            retrieved_source_ids=[chunk.source_id for chunk in result.retrieved_chunks],
        )

    metrics = evaluate_with_deepeval(
        case=case,
        result=result,
        mode=mode,
        judge_model=judge_model,
        answer_relevancy_threshold=answer_relevancy_threshold,
        faithfulness_threshold=faithfulness_threshold,
    )
    return DeepEvalCaseResult(
        mode=mode,
        case_id=case.case_id,
        skipped=False,
        skip_reason=None,
        answer=result.answer,
        status=result.status,
        metrics=metrics,
        retrieved_chunk_ids=[chunk.chunk_id for chunk in result.retrieved_chunks],
        retrieved_source_ids=[chunk.source_id for chunk in result.retrieved_chunks],
    )


def evaluate_with_deepeval(
    *,
    case: GoldenBenchCase,
    result: ChatAnswer,
    mode: str,
    judge_model: str,
    answer_relevancy_threshold: float,
    faithfulness_threshold: float,
) -> list[DeepEvalMetricResult]:
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.metrics import FaithfulnessMetric
    from deepeval.test_case import LLMTestCase

    retrieval_context = [chunk.text for chunk in result.retrieved_chunks]
    expected_output = build_expected_output(case)
    test_case = LLMTestCase(
        input=case.question,
        actual_output=result.answer,
        expected_output=expected_output,
        retrieval_context=retrieval_context,
    )

    metric_results: list[DeepEvalMetricResult] = []
    answer_relevancy = AnswerRelevancyMetric(
        threshold=answer_relevancy_threshold,
        model=judge_model,
        include_reason=True,
        async_mode=False,
    )
    answer_relevancy.measure(test_case)
    metric_results.append(
        capture_metric_result("answer_relevancy", answer_relevancy)
    )

    if mode == "rag" and retrieval_context and result.status != "unknown":
        faithfulness = FaithfulnessMetric(
            threshold=faithfulness_threshold,
            model=judge_model,
            include_reason=True,
            async_mode=False,
        )
        faithfulness.measure(test_case)
        metric_results.append(
            capture_metric_result("faithfulness", faithfulness)
        )

    return metric_results


def capture_metric_result(name: str, metric: Any) -> DeepEvalMetricResult:
    success = getattr(metric, "success", None)
    if success is None and hasattr(metric, "is_successful"):
        try:
            success = metric.is_successful()
        except Exception:
            success = None
    return DeepEvalMetricResult(
        name=name,
        score=getattr(metric, "score", None),
        success=success,
        threshold=getattr(metric, "threshold", None),
        reason=getattr(metric, "reason", None),
    )


def build_expected_output(case: GoldenBenchCase) -> str | None:
    if not case.expected_answer_contains:
        return None
    return "；".join(case.expected_answer_contains)


def summarize_deepeval_results(
    results: list[DeepEvalCaseResult],
    *,
    mode: str,
    judge_model: str,
) -> dict[str, Any]:
    executed = [result for result in results if not result.skipped]
    skipped = [result for result in results if result.skipped]
    metric_summary: dict[str, dict[str, Any]] = {}

    for result in executed:
        for metric in result.metrics:
            summary = metric_summary.setdefault(
                metric.name,
                {
                    "count": 0,
                    "success_count": 0,
                    "score_sum": 0.0,
                    "score_count": 0,
                },
            )
            summary["count"] += 1
            if metric.success:
                summary["success_count"] += 1
            if metric.score is not None:
                summary["score_sum"] += float(metric.score)
                summary["score_count"] += 1

    metrics_output: dict[str, Any] = {}
    for name, summary in metric_summary.items():
        metrics_output[name] = {
            "count": summary["count"],
            "success_count": summary["success_count"],
            "success_rate": (
                summary["success_count"] / summary["count"] if summary["count"] else 0.0
            ),
            "average_score": (
                summary["score_sum"] / summary["score_count"]
                if summary["score_count"]
                else None
            ),
        }

    return {
        "mode": mode,
        "judge_model": judge_model,
        "total": len(results),
        "executed": len(executed),
        "skipped": len(skipped),
        "metrics": metrics_output,
        "results": [result.to_dict() for result in results],
    }
