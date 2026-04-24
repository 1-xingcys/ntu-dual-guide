from __future__ import annotations

import re

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


CREDIT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)")


class RequiredCoursesGoldChunker(BaseGoldChunker):
    chunker_name = "required_courses_chunker"
    chunker_version = "v3"

    def build_document(self, silver_document: dict) -> dict:
        content = silver_document["content"]
        chunks: list[GoldChunk] = []
        department_code = content.get("department_code")
        department_name = content.get("department_name")
        admission_year = content.get("admission_year")
        grade = content.get("grade")
        grade_label = content.get("grade_label") or grade or "未知年級"
        department_context = build_department_context(
            department_name=department_name,
            department_code=department_code,
        )
        courses = content["courses"]
        course_names = [course["chinese_name"] for course in courses]
        total_credits = sum_credits(courses)

        chunks.append(
            GoldChunk(
                chunk_id="{0}-list".format(silver_document["source_id"]),
                chunk_type="required_courses_list",
                title="{0} {1} {2}學年度 必修課程清單".format(
                    department_name or department_code or "系所",
                    grade_label,
                    admission_year or "未知",
                ),
                text=render_list_text(
                    department_context=department_context,
                    admission_year=admission_year,
                    grade_label=grade_label,
                    course_names=course_names,
                    total_credits=total_credits,
                ),
                order=1,
                metadata={
                    "department_code": department_code,
                    "department_name": department_name,
                    "admission_year": admission_year,
                    "grade": grade,
                    "grade_label": grade_label,
                    "course_count": len(course_names),
                    "course_names": course_names,
                    "total_credits": total_credits,
                },
            )
        )

        for index, course in enumerate(courses, start=1):
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-course-{1:03d}".format(silver_document["source_id"], index),
                    chunk_type="required_course",
                    title=course["chinese_name"],
                    text=render_course_text(
                        department_context=department_context,
                        admission_year=admission_year,
                        grade_label=grade_label,
                        course=course,
                    ),
                    order=len(chunks) + 1,
                    metadata={
                        "department_code": department_code,
                        "department_name": department_name,
                        "admission_year": admission_year,
                        "grade": grade,
                        "grade_label": grade_label,
                        "course_code": course["course_code"],
                        "course_identifier": course.get("course_identifier"),
                        "chinese_name": course["chinese_name"],
                        "credits": course["credits"],
                        "group": course.get("group"),
                        "recognition_scope": course.get("recognition_scope"),
                    },
                )
            )

        for index, note in enumerate(content["notes"], start=1):
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-note-{1:03d}".format(silver_document["source_id"], index),
                    chunk_type="required_courses_note",
                    title="備註 {0}".format(index),
                    text=(
                        "{department_context}{admission_year}學年度入學學生，{grade_label}系訂必修科目備註：{note}"
                    ).format(
                        department_context=department_context,
                        admission_year=admission_year or "未知",
                        grade_label=grade_label,
                        note=note,
                    ),
                    order=len(chunks) + 1,
                    metadata={
                        "department_code": department_code,
                        "department_name": department_name,
                        "admission_year": admission_year,
                        "grade": grade,
                        "grade_label": grade_label,
                        "note_index": index,
                    },
                )
            )

        document = GoldDocument(
            dataset_version=silver_document["dataset_version"],
            source_id=silver_document["source_id"],
            doc_type=silver_document["doc_type"],
            title=silver_document["title"],
            source_path=silver_document["source_path"],
            source_hash=silver_document["source_hash"],
            silver_processing_fingerprint=silver_document["processing_fingerprint"],
            chunker_name=self.chunker_name,
            chunker_version=self.chunker_version,
            processing_fingerprint=self.processing_fingerprint(
                silver_document["processing_fingerprint"]
            ),
            chunks=chunks,
            source_url=silver_document.get("source_url"),
            language=silver_document.get("language", "zh-TW"),
            authority_level=silver_document.get("authority_level", "primary"),
        )
        return document.to_dict()


def render_list_text(
    *,
    department_context: str,
    admission_year: str | None,
    grade_label: str,
    course_names: list[str],
    total_credits: float | None,
) -> str:
    year_text = admission_year or "未知"
    if not course_names:
        return "{0}{1}學年度入學學生，{2}系訂必修科目查無課程資料。".format(
            department_context, year_text, grade_label
        )
    credits_sentence = ""
    if total_credits is not None:
        credits_sentence = "、合計{0}學分".format(format_credits(total_credits))
    return (
        "{department_context}{year}學年度入學學生，{grade_label}系訂必修共{count}門{credits_sentence}。"
        "必修課程：{course_list}。"
    ).format(
        department_context=department_context,
        year=year_text,
        grade_label=grade_label,
        count=len(course_names),
        credits_sentence=credits_sentence,
        course_list="、".join(course_names),
    )


def render_course_text(
    *,
    department_context: str,
    admission_year: str | None,
    grade_label: str,
    course: dict,
) -> str:
    parts = [
        "課號{0}".format(course["course_code"]),
    ]
    if course.get("course_identifier"):
        parts.append("課程識別碼{0}".format(course["course_identifier"]))
    parts.append("{0}學分".format(course["credits"]))
    if course.get("group"):
        parts.append("群組別{0}".format(course["group"]))
    if course.get("recognition_scope"):
        parts.append("必修認可範圍{0}".format(course["recognition_scope"]))
    return (
        "{department_context}{year}學年度入學學生，{grade_label}系訂必修科目「{chinese_name}」"
        "（{english_name}）：{details}。"
    ).format(
        department_context=department_context,
        year=admission_year or "未知",
        grade_label=grade_label,
        chinese_name=course["chinese_name"],
        english_name=course["english_name"],
        details="，".join(parts),
    )


def sum_credits(courses: list[dict]) -> float | None:
    total = 0.0
    found = False
    for course in courses:
        raw = course.get("credits")
        if raw is None:
            continue
        match = CREDIT_PATTERN.search(str(raw))
        if not match:
            continue
        total += float(match.group(1))
        found = True
    return total if found else None


def format_credits(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return "{0:.1f}".format(value)


def build_department_context(*, department_name: str | None, department_code: str | None) -> str:
    aliases: list[str] = []
    if department_name and "資訊工程" in department_name:
        aliases = ["資工系", "資工", "CSIE"]
    elif department_name and "經濟" in department_name:
        aliases = ["經濟系", "經濟", "ECON"]
    if department_code:
        aliases.append(str(department_code))
    if department_name and aliases:
        return "{0}（{1}）".format(department_name, "、".join(dict.fromkeys(aliases)))
    if department_name:
        return department_name
    if department_code:
        return "系所代碼{0}".format(department_code)
    return "未知系所"
