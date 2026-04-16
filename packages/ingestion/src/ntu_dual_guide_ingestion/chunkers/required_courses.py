from __future__ import annotations

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class RequiredCoursesGoldChunker(BaseGoldChunker):
    chunker_name = "required_courses_chunker"
    chunker_version = "v1"

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

        chunks.append(
            GoldChunk(
                chunk_id="{0}-overview".format(silver_document["source_id"]),
                chunk_type="required_courses_overview",
                title="{0} 概覽".format(silver_document["title"]),
                text=(
                    "{department_context}{admission_year}學年度入學學生，{grade_label}系訂必修科目及學分表。"
                    "本頁共列出{course_count}門課程。"
                ).format(
                    department_context=department_context,
                    admission_year=admission_year or "未知",
                    grade_label=grade_label,
                    course_count=len(content["courses"]),
                ),
                order=1,
                metadata={
                    "department_code": department_code,
                    "department_name": department_name,
                    "admission_year": admission_year,
                    "grade": grade,
                    "grade_label": grade_label,
                    "course_count": len(content["courses"]),
                },
            )
        )

        for index, course in enumerate(content["courses"], start=1):
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-course-{1:03d}".format(silver_document["source_id"], index),
                    chunk_type="required_course",
                    title=course["chinese_name"],
                    text=(
                        "{department_context}{admission_year}學年度入學學生，{grade_label}系訂必修課程："
                        "{chinese_name}（{english_name}），課號{course_code}"
                        "{identifier_part}，{credits}學分，群組別{group_value}，必修認可範圍{recognition_scope}。"
                    ).format(
                        department_context=department_context,
                        admission_year=admission_year or "未知",
                        grade_label=grade_label,
                        chinese_name=course["chinese_name"],
                        english_name=course["english_name"],
                        course_code=course["course_code"],
                        identifier_part=render_identifier(course.get("course_identifier")),
                        credits=course["credits"],
                        group_value=course.get("group") or "無",
                        recognition_scope=course.get("recognition_scope") or "未提供",
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


def render_identifier(course_identifier: str | None) -> str:
    if not course_identifier:
        return ""
    return "，課程識別碼{0}".format(course_identifier)


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
