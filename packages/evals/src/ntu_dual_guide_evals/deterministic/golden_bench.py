from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GoldenBenchCase:
    case_id: str
    question: str
    expected_answer: str | None
    expected_status: str
    allow_unknown: bool
    expected_answer_contains: list[str]
    expected_source_ids_any: list[str]
    expected_retrieved_chunk_ids_any: list[str]
    expected_chunk_groups: list[list[str]]
    tags: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoldenBenchCase":
        expected_chunk_groups = [
            list(group)
            for group in payload.get("expected_chunk_groups", [])
            if group
        ]
        expected_retrieved_chunk_ids_any = list(
            payload.get("expected_retrieved_chunk_ids_any", [])
        )
        if not expected_retrieved_chunk_ids_any:
            expected_retrieved_chunk_ids_any = sorted(
                {chunk_id for group in expected_chunk_groups for chunk_id in group}
            )
        return cls(
            case_id=payload["case_id"],
            question=payload["question"],
            expected_answer=payload.get("expected_answer"),
            expected_status=payload.get("expected_status", "answered"),
            allow_unknown=bool(payload.get("allow_unknown", False)),
            expected_answer_contains=list(payload.get("expected_answer_contains", [])),
            expected_source_ids_any=list(payload.get("expected_source_ids_any", [])),
            expected_retrieved_chunk_ids_any=expected_retrieved_chunk_ids_any,
            expected_chunk_groups=expected_chunk_groups,
            tags=list(payload.get("tags", [])),
        )


def load_golden_bench(dataset_path: Path) -> list[GoldenBenchCase]:
    cases: list[GoldenBenchCase] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(GoldenBenchCase.from_dict(json.loads(line)))
    return cases
