from __future__ import annotations

import re
from typing import Any

from ntu_dual_guide_ingestion.normalizers.base import BaseSilverNormalizer
from ntu_dual_guide_ingestion.silver_schema import CurriculumRequiredContent
from ntu_dual_guide_ingestion.silver_schema import CurriculumTermLimit
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import normalize_fragment


TITLE_PATTERN = re.compile(
    r"(?P<department_code>\d+)\s*(?P<department_name>.+?)畢業應修學分統計表,\s*(?P<admission_year>\d+)學年度"
)
GROUP_TABLE_HEADER = "中文名稱"


class BronzeCurriculumRequiredNormalizer(BaseSilverNormalizer):
    normalizer_name = "bronze_curriculum_required_normalizer"
    normalizer_version = "v1"

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_curriculum_required(bronze_document)
        source_id = "{0}-credit-required-{1}".format(
            parsed["department_code"] or "department",
            parsed["admission_year"] or "unknown",
        )
        document = SilverDocument(
            dataset_version=bronze_document["dataset_version"],
            source_id=source_id,
            doc_type="curriculum_required_summary",
            title=parsed["title"],
            source_path=bronze_document["raw_path"],
            source_hash=bronze_document["source_hash"],
            parser_name=bronze_document["parser_name"],
            parser_version=bronze_document["parser_version"],
            normalizer_version=self.normalizer_version,
            processing_fingerprint=self.processing_fingerprint(
                bronze_document["processing_fingerprint"]
            ),
            authority_level="primary",
            content=CurriculumRequiredContent(
                department_code=parsed["department_code"],
                department_name=parsed["department_name"],
                admission_year=parsed["admission_year"],
                graduation_total_credits=parsed["graduation_total_credits"],
                required_major_credits=parsed["required_major_credits"],
                common_and_general_credits=parsed["common_and_general_credits"],
                elective_credits=parsed["elective_credits"],
                term_limits=parsed["term_limits"],
                notes=parsed["notes"],
            ),
            source_url=bronze_document.get("source_url"),
        )
        return document.to_dict()


def parse_curriculum_required(bronze_document: dict[str, Any]) -> dict[str, Any]:
    title = find_curriculum_title(bronze_document)
    department_code, department_name, admission_year = parse_curriculum_title(title)
    table_rows = [block for block in bronze_document["content"]["blocks"] if block["block_type"] == "table_row"]

    term_limits: list[CurriculumTermLimit] = []
    current_grade = None
    required_major_credits = None
    common_and_general_credits = None
    elective_credits = None
    graduation_total_credits = None
    notes: list[str] = []
    collecting_notes = False

    for row in table_rows:
        cells = row.get("attributes", {}).get("cells") or []
        cells = [normalize_fragment(cell) for cell in cells if normalize_fragment(cell)]
        if not cells:
            continue
        first = cells[0]
        if first == "年級" or first == "學分下限":
            continue
        if first == GROUP_TABLE_HEADER:
            collecting_notes = False
            continue
        if first == "合計" and len(cells) >= 4:
            required_major_credits = cells[1]
            common_and_general_credits = cells[2]
            elective_credits = cells[3]
            continue
        if first == "畢業時學生應修最低學分總數" and len(cells) >= 2:
            graduation_total_credits = cells[1]
            continue
        if first in {"選課特別規定", "通識相關規定"} and len(cells) >= 2:
            notes.append("{0}: {1}".format(first, cells[1]))
            collecting_notes = True
            continue
        if collecting_notes and is_curriculum_note_row(cells):
            notes.append(join_note_cells(cells))
            continue
        if len(cells) >= 5 and "學期" in cells[1]:
            current_grade = cells[0]
            term_limits.append(
                CurriculumTermLimit(
                    grade=current_grade,
                    term=cells[1],
                    min_credits=cells[2],
                    max_credits=cells[3],
                    required_major_credits=cells[4],
                )
            )
            continue
        if len(cells) == 4 and current_grade:
            if "年級" in cells[0]:
                term_limits.append(
                    CurriculumTermLimit(
                        grade=cells[0],
                        term="",
                        min_credits=cells[1],
                        max_credits=cells[2],
                        required_major_credits=cells[3],
                    )
                )
                continue
            term_limits.append(
                CurriculumTermLimit(
                    grade=current_grade,
                    term=cells[0],
                    min_credits=cells[1],
                    max_credits=cells[2],
                    required_major_credits=cells[3],
                )
            )

    return {
        "title": title,
        "department_code": department_code,
        "department_name": department_name,
        "admission_year": admission_year,
        "graduation_total_credits": graduation_total_credits,
        "required_major_credits": required_major_credits,
        "common_and_general_credits": common_and_general_credits,
        "elective_credits": elective_credits,
        "term_limits": term_limits,
        "notes": notes,
    }


def is_curriculum_note_row(cells: list[str]) -> bool:
    first = cells[0]
    return bool(
        re.match(r"^[一二三四五六七八九十]+、", first)
        or re.match(r"^\d+\.", first)
    ) and len(cells) <= 2


def join_note_cells(cells: list[str]) -> str:
    if len(cells) == 1:
        return cells[0]
    return "{0}: {1}".format(cells[0], " ".join(cells[1:]))


def find_curriculum_title(bronze_document: dict[str, Any]) -> str:
    for block in bronze_document["content"]["blocks"]:
        text = normalize_fragment(block["text"])
        if "畢業應修學分統計表" in text:
            return text
    return bronze_document["content"].get("title") or bronze_document["file_name"]


def parse_curriculum_title(title: str) -> tuple[str | None, str | None, str | None]:
    match = TITLE_PATTERN.search(title)
    if not match:
        return None, None, None
    return (
        match.group("department_code"),
        normalize_fragment(match.group("department_name")),
        match.group("admission_year"),
    )
