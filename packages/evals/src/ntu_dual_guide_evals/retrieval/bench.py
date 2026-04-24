from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path


CASE_TYPE_PREFIXES = (
    "single-fact",
    "multi-fact-compare",
    "misleading-single-fact",
)


@dataclass
class RetrievalCase:
    """One retrieval bench case.

    `expected_chunk_groups` uses a DNF structure: a list of groups, where each
    group is a list of chunk_ids that must ALL appear in top-k for that group
    to be satisfied. The case counts as a hit if AT LEAST ONE group is fully
    satisfied. This expresses both AND (single group with N chunks) and OR
    (N groups with one chunk each), and combinations.
    """

    case_id: str
    question: str
    expected_chunk_groups: list[list[str]]
    expected_source_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def case_type(self) -> str:
        for prefix in CASE_TYPE_PREFIXES:
            if self.case_id.startswith(prefix + "-"):
                return prefix
        return "unknown"

    @property
    def all_expected_chunk_ids(self) -> set[str]:
        ids: set[str] = set()
        for group in self.expected_chunk_groups:
            ids.update(group)
        return ids


def load_retrieval_bench(path: Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    with open(path, "r", encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            groups = payload.get("expected_chunk_groups") or []
            normalized_groups = [list(group) for group in groups if group]
            cases.append(
                RetrievalCase(
                    case_id=payload["case_id"],
                    question=payload["question"],
                    expected_chunk_groups=normalized_groups,
                    expected_source_ids=list(payload.get("expected_source_ids") or []),
                    tags=list(payload.get("tags") or []),
                )
            )
    return cases
