from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ntu_dual_guide_ingestion.chunkers.curriculum_required import CurriculumRequiredGoldChunker
from ntu_dual_guide_ingestion.chunkers.dual_major_policy import DualMajorPolicyGoldChunker
from ntu_dual_guide_ingestion.chunkers.faq import FaqGoldChunker
from ntu_dual_guide_ingestion.chunkers.required_courses import RequiredCoursesGoldChunker
from ntu_dual_guide_ingestion.chunkers.sectioned_source import SectionedSourceGoldChunker


class SilverToGoldRouter:
    def __init__(self) -> None:
        self.faq_chunker = FaqGoldChunker()
        self.dual_major_policy_chunker = DualMajorPolicyGoldChunker()
        self.curriculum_required_chunker = CurriculumRequiredGoldChunker()
        self.required_courses_chunker = RequiredCoursesGoldChunker()
        self.sectioned_source_chunker = SectionedSourceGoldChunker()

    def resolve(self, silver_document: dict):
        doc_type = silver_document["doc_type"]
        if doc_type == "faq":
            return self.faq_chunker
        if doc_type == "dual_major_policy":
            return self.dual_major_policy_chunker
        if doc_type == "curriculum_required_summary":
            return self.curriculum_required_chunker
        if doc_type == "curriculum_required_courses":
            return self.required_courses_chunker
        if doc_type in {"econ_portal_page", "handbook", "ntu_policy_info_page"}:
            return self.sectioned_source_chunker
        raise ValueError("No gold chunker configured for silver doc_type: {0}".format(doc_type))

    def build_gold_document(self, silver_path: Path) -> dict:
        silver_document = json.loads(silver_path.read_text(encoding="utf-8"))
        chunker = self.resolve(silver_document)
        return chunker.build_document(silver_document)


def iter_silver_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*.json")):
        if path.is_file():
            yield path


def gold_output_path(silver_path: Path, silver_root: Path, gold_root: Path) -> Path:
    relative_path = silver_path.relative_to(silver_root)
    return gold_root / relative_path


def write_gold_document(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
