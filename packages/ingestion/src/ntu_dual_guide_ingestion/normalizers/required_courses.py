from __future__ import annotations

import re
from typing import Any

from ntu_dual_guide_ingestion.normalizers.base import BaseSilverNormalizer
from ntu_dual_guide_ingestion.silver_schema import CurriculumRequiredCoursesContent
from ntu_dual_guide_ingestion.silver_schema import RequiredCourseItem
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import normalize_fragment


TITLE_PATTERN = re.compile(
    r"(?P<department_code>\d+)\s*(?P<department_name>.+?)\s*"
    r"(?P<grade_label>[一二三四五六七八九十不分]+年級)"
    r"系訂必修科目及學分表,\s*(?P<admission_year>\d+)學年度入學學生開始實施"
)
FILENAME_PATTERN = re.compile(
    r"(?P<department_code>\d+)-(?P<admission_year>\d+)學年度-(?P<grade>\d+)年級系訂必修科目及學分表"
)
TOP_TABLE_PATTERN = re.compile(
    r"<table[^>]*class='totcrd-top-table[^']*'[^>]*>(?P<body>.*?)</table>",
    re.S,
)
BOTTOM_NOTE_PATTERN = re.compile(
    r"<table[^>]*class='totcrd-bottom-table[^']*'[^>]*>.*?<td[^>]*class='pd8'[^>]*>(?P<body>.*?)</td>",
    re.S,
)
CELL_PATTERN = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG_PATTERN = re.compile(r"<[^>]+>")
BR_PATTERN = re.compile(r"<br\s*/?>", re.I)


class BronzeRequiredCoursesNormalizer(BaseSilverNormalizer):
    normalizer_name = "bronze_required_courses_normalizer"
    normalizer_version = "v1"

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_required_courses(bronze_document)
        source_id = "{0}-required-courses-{1}-grade-{2}".format(
            parsed["department_code"] or "department",
            parsed["admission_year"] or "unknown",
            parsed["grade"] or "unknown",
        )
        document = SilverDocument(
            dataset_version=bronze_document["dataset_version"],
            source_id=source_id,
            doc_type="curriculum_required_courses",
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
            content=CurriculumRequiredCoursesContent(
                department_code=parsed["department_code"],
                department_name=parsed["department_name"],
                admission_year=parsed["admission_year"],
                grade=parsed["grade"],
                grade_label=parsed["grade_label"],
                courses=parsed["courses"],
                notes=parsed["notes"],
            ),
            source_url=bronze_document.get("source_url"),
        )
        return document.to_dict()


def parse_required_courses(bronze_document: dict[str, Any]) -> dict[str, Any]:
    raw_path = bronze_document["raw_path"]
    html_text = open(raw_path, "r", encoding="utf-8").read()
    title = extract_required_courses_title(html_text, bronze_document)
    department_code, department_name, grade_label, admission_year = parse_required_courses_title(title)
    grade = parse_grade_from_filename(bronze_document["file_name"])
    courses = extract_course_rows(html_text)
    notes = extract_notes(html_text)
    return {
        "title": title,
        "department_code": department_code,
        "department_name": department_name,
        "admission_year": admission_year,
        "grade": grade,
        "grade_label": grade_label or infer_grade_label(grade),
        "courses": courses,
        "notes": notes,
    }


def extract_required_courses_title(html_text: str, bronze_document: dict[str, Any]) -> str:
    match = re.search(r"<h1>(?P<prefix>.*?)<span>(?P<body>.*?)</span></h1>", html_text, re.S)
    if not match:
        return bronze_document["file_name"]
    merged = "{0} {1}".format(match.group("prefix"), match.group("body"))
    merged = BR_PATTERN.sub(" ", merged)
    merged = TAG_PATTERN.sub(" ", merged)
    return normalize_fragment(merged)


def parse_required_courses_title(title: str) -> tuple[str | None, str | None, str | None, str | None]:
    match = TITLE_PATTERN.search(title)
    if not match:
        return None, None, None, None
    return (
        match.group("department_code"),
        normalize_fragment(match.group("department_name")),
        normalize_fragment(match.group("grade_label")),
        match.group("admission_year"),
    )


def parse_grade_from_filename(file_name: str) -> str | None:
    match = FILENAME_PATTERN.search(file_name)
    return match.group("grade") if match else None


def infer_grade_label(grade: str | None) -> str | None:
    mapping = {
        "1": "一年級",
        "2": "二年級",
        "3": "三年級",
        "4": "四年級",
    }
    if grade is None:
        return None
    return mapping.get(grade, "{0}年級".format(grade))


def extract_course_rows(html_text: str) -> list[RequiredCourseItem]:
    match = TOP_TABLE_PATTERN.search(html_text)
    if not match:
        return []
    cells = [clean_cell(cell) for cell in CELL_PATTERN.findall(match.group("body"))]
    if len(cells) < 6:
        return []
    row_width = 6
    data_cells = cells[row_width:]
    courses: list[RequiredCourseItem] = []
    for index in range(0, len(data_cells), row_width):
        row = data_cells[index : index + row_width]
        if len(row) < row_width:
            continue
        course_code, course_identifier = split_course_code_identifier(row[0])
        if not course_code or not row[1]:
            continue
        courses.append(
            RequiredCourseItem(
                course_code=course_code,
                course_identifier=course_identifier,
                chinese_name=row[1],
                english_name=row[2],
                credits=row[3],
                group=row[4] or None,
                recognition_scope=row[5] or None,
            )
        )
    return courses


def extract_notes(html_text: str) -> list[str]:
    match = BOTTOM_NOTE_PATTERN.search(html_text)
    if not match:
        return []
    note_html = BR_PATTERN.sub("\n", match.group("body"))
    note_text = TAG_PATTERN.sub(" ", note_html)
    lines = [normalize_fragment(line) for line in note_text.splitlines()]
    return [line for line in lines if line]


def clean_cell(cell_html: str) -> str:
    cell_html = BR_PATTERN.sub(" ", cell_html)
    cell_text = TAG_PATTERN.sub(" ", cell_html)
    return normalize_fragment(cell_text)


def split_course_code_identifier(raw: str) -> tuple[str, str | None]:
    parts = raw.split(maxsplit=1)
    if not parts:
        return "", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]
