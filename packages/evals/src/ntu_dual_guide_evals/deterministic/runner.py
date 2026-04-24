from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ntu_dual_guide_evals.deterministic.golden_bench import GoldenBenchCase
from ntu_dual_guide_rag.models import ChatAnswer


class AnsweringService(Protocol):
    def answer(self, question: str) -> ChatAnswer:
        ...


@dataclass
class CaseResult:
    mode: str
    case_id: str
    passed: bool
    errored: bool
    error_message: str | None
    status_ok: bool
    answer_contains_ok: bool
    source_hit_ok: bool
    retrieval_hit_ok: bool
    source_hit_checked: bool
    retrieval_hit_checked: bool
    answer: str
    citations: list[dict[str, Any]]
    retrieved_chunk_ids: list[str]
    retrieved_source_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "case_id": self.case_id,
            "passed": self.passed,
            "errored": self.errored,
            "error_message": self.error_message,
            "status_ok": self.status_ok,
            "answer_contains_ok": self.answer_contains_ok,
            "source_hit_ok": self.source_hit_ok,
            "retrieval_hit_ok": self.retrieval_hit_ok,
            "source_hit_checked": self.source_hit_checked,
            "retrieval_hit_checked": self.retrieval_hit_checked,
            "answer": self.answer,
            "citations": self.citations,
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "retrieved_source_ids": self.retrieved_source_ids,
        }


def run_case(service: AnsweringService, case: GoldenBenchCase, *, mode: str = "rag") -> CaseResult:
    result = service.answer(case.question)
    return evaluate_case(case, result, mode=mode)


def evaluate_case(case: GoldenBenchCase, result: ChatAnswer, *, mode: str = "rag") -> CaseResult:
    normalized_answer = result.answer.replace(" ", "")
    expected_answer_contains = [item.replace(" ", "") for item in case.expected_answer_contains]
    answer_contains_ok = all(item in normalized_answer for item in expected_answer_contains)
    status_ok = result.status == case.expected_status or (case.allow_unknown and result.status == "unknown")

    retrieved_chunk_ids = [chunk.chunk_id for chunk in result.retrieved_chunks]
    retrieved_source_ids = [chunk.source_id for chunk in result.retrieved_chunks]
    retrieval_checks_enabled = mode == "rag"

    source_hit_ok = (
        True
        if not retrieval_checks_enabled or not case.expected_source_ids_any
        else any(source_id in retrieved_source_ids for source_id in case.expected_source_ids_any)
    )
    retrieval_hit_ok = (
        True
        if not retrieval_checks_enabled or not case.expected_retrieved_chunk_ids_any
        else any(chunk_id in retrieved_chunk_ids for chunk_id in case.expected_retrieved_chunk_ids_any)
    )
    passed = status_ok and answer_contains_ok and source_hit_ok and retrieval_hit_ok

    return CaseResult(
        mode=mode,
        case_id=case.case_id,
        passed=passed,
        errored=False,
        error_message=None,
        status_ok=status_ok,
        answer_contains_ok=answer_contains_ok,
        source_hit_ok=source_hit_ok,
        retrieval_hit_ok=retrieval_hit_ok,
        source_hit_checked=retrieval_checks_enabled and bool(case.expected_source_ids_any),
        retrieval_hit_checked=retrieval_checks_enabled and bool(case.expected_retrieved_chunk_ids_any),
        answer=result.answer,
        citations=[citation.to_dict() for citation in result.citations],
        retrieved_chunk_ids=retrieved_chunk_ids,
        retrieved_source_ids=retrieved_source_ids,
    )


def error_case_result(
    case: GoldenBenchCase,
    *,
    mode: str,
    error_message: str,
) -> CaseResult:
    return CaseResult(
        mode=mode,
        case_id=case.case_id,
        passed=False,
        errored=True,
        error_message=error_message,
        status_ok=False,
        answer_contains_ok=False,
        source_hit_ok=False,
        retrieval_hit_ok=False,
        source_hit_checked=False,
        retrieval_hit_checked=False,
        answer="",
        citations=[],
        retrieved_chunk_ids=[],
        retrieved_source_ids=[],
    )


def summarize_results(results: list[CaseResult], *, mode: str) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    errored = sum(1 for result in results if result.errored)
    source_checked = sum(1 for result in results if result.source_hit_checked)
    retrieval_checked = sum(1 for result in results if result.retrieval_hit_checked)
    return {
        "mode": mode,
        "total": total,
        "passed": passed,
        "errored": errored,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "source_checks_enabled_cases": source_checked,
        "retrieval_checks_enabled_cases": retrieval_checked,
        "results": [result.to_dict() for result in results],
    }

