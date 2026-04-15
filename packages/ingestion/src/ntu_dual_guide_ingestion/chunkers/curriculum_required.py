from __future__ import annotations

import re

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class CurriculumRequiredGoldChunker(BaseGoldChunker):
    chunker_name = "curriculum_required_chunker"
    chunker_version = "v2"

    def build_document(self, silver_document: dict) -> dict:
        content = silver_document["content"]
        chunks: list[GoldChunk] = []

        chunks.append(
            GoldChunk(
                chunk_id="{0}-overview".format(silver_document["source_id"]),
                chunk_type="curriculum_overview",
                title="{0} 概覽".format(silver_document["title"]),
                text=(
                    "{admission_year}學年度入學，{department_name}({department_code})畢業應修最低學分總數為"
                    "{graduation_total_credits}學分。系訂必修{required_major_credits}學分，"
                    "共同必修加通識{common_and_general_credits}學分，選修{elective_credits}學分。"
                ).format(**content),
                order=1,
                metadata={
                    "department_code": content.get("department_code"),
                    "department_name": content.get("department_name"),
                    "admission_year": content.get("admission_year"),
                    "graduation_total_credits": content.get("graduation_total_credits"),
                },
            )
        )

        for term_limit in content["term_limits"]:
            order = len(chunks) + 1
            grade = term_limit["grade"]
            term = term_limit["term"] or "全年"
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-term-{1:03d}".format(silver_document["source_id"], order),
                    chunk_type="curriculum_term_limit",
                    title="{0} {1} 修課限制".format(grade, term),
                    text=(
                        "{department_name} {admission_year}學年度入學學生，{grade}{term}"
                        "每學期修習學分下限{min_credits}、上限{max_credits}，"
                        "系訂必修{required_major_credits}學分。"
                    ).format(
                        department_name=content.get("department_name"),
                        admission_year=content.get("admission_year"),
                        grade=grade,
                        term=term,
                        min_credits=term_limit["min_credits"],
                        max_credits=term_limit["max_credits"],
                        required_major_credits=term_limit["required_major_credits"],
                    ),
                    order=order,
                    metadata=term_limit,
                )
            )

        for index, note in enumerate(content["notes"], start=1):
            note_chunks = build_note_chunks(
                silver_document=silver_document,
                content=content,
                note=note,
                note_index=index,
                start_order=len(chunks) + 1,
            )
            chunks.extend(note_chunks)

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


def build_note_chunks(
    *,
    silver_document: dict,
    content: dict,
    note: str,
    note_index: int,
    start_order: int,
) -> list[GoldChunk]:
    department_code = content.get("department_code")
    department_name = content.get("department_name")
    admission_year = content.get("admission_year")
    department_aliases = infer_department_aliases(department_name, department_code)
    note_items = split_note_items(note)

    if not note_items:
        return [
            GoldChunk(
                chunk_id="{0}-note-{1:03d}".format(silver_document["source_id"], note_index),
                chunk_type="curriculum_note",
                title="規定說明 {0}".format(note_index),
                text=render_note_text(
                    department_name=department_name,
                    department_aliases=department_aliases,
                    department_code=department_code,
                    admission_year=admission_year,
                    body=note,
                    note_index=note_index,
                    note_item_index=None,
                ),
                order=start_order,
                metadata={
                    "department_code": department_code,
                    "department_name": department_name,
                    "department_aliases": department_aliases,
                    "admission_year": admission_year,
                    "note_index": note_index,
                },
            )
        ]

    chunks: list[GoldChunk] = []
    for offset, note_item in enumerate(note_items):
        order = start_order + offset
        chunks.append(
            GoldChunk(
                chunk_id="{0}-note-{1:03d}-item-{2:03d}".format(
                    silver_document["source_id"],
                    note_index,
                    note_item["item_number"],
                ),
                chunk_type="curriculum_note_item",
                title="規定說明 {0}-({1})".format(note_index, note_item["item_number"]),
                text=render_note_text(
                    department_name=department_name,
                    department_aliases=department_aliases,
                    department_code=department_code,
                    admission_year=admission_year,
                    body=note_item["text"],
                    note_index=note_index,
                    note_item_index=note_item["item_number"],
                ),
                order=order,
                metadata={
                    "department_code": department_code,
                    "department_name": department_name,
                    "department_aliases": department_aliases,
                    "admission_year": admission_year,
                    "note_index": note_index,
                    "note_item_index": note_item["item_number"],
                },
            )
        )
    return chunks


def split_note_items(note: str) -> list[dict]:
    chinese_prefix_match = re.match(r"^(?P<prefix>[一二三四五六七八九十]+、)(?P<body>.*)$", note)
    if chinese_prefix_match:
        body = chinese_prefix_match.group("body").strip()
        paren_items = split_parenthesized_items(body)
        if paren_items:
            return paren_items
    return []


def split_parenthesized_items(text: str) -> list[dict]:
    matches = list(re.finditer(r"\((\d+)\)", text))
    if len(matches) < 2:
        return []
    items: list[dict] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item_text = text[start:end].strip()
        if not item_text:
            continue
        items.append(
            {
                "item_number": int(match.group(1)),
                "text": item_text,
            }
        )
    return items


def render_note_text(
    *,
    department_name: str | None,
    department_aliases: list[str],
    department_code: str | None,
    admission_year: str | None,
    body: str,
    note_index: int,
    note_item_index: int | None,
) -> str:
    department_context = build_department_context(
        department_name=department_name,
        department_aliases=department_aliases,
        department_code=department_code,
    )
    if note_item_index is None:
        return "{0}{1}學年度入學學生畢業應修學分統計表規定，第{2}點：{3}".format(
            department_context,
            admission_year or "未知",
            note_index,
            body,
        )
    return "{0}{1}學年度入學學生畢業應修學分統計表規定，第{2}點第({3})款：{4}".format(
        department_context,
        admission_year or "未知",
        note_index,
        note_item_index,
        body,
    )


def build_department_context(
    *,
    department_name: str | None,
    department_aliases: list[str],
    department_code: str | None,
) -> str:
    if department_name and department_aliases:
        alias_parts = [alias for alias in department_aliases if alias != department_code]
        if department_code:
            alias_parts.append(department_code)
        return "{0}（{1}）".format(
            department_name,
            "、".join(alias_parts) or "未知代碼",
        )
    if department_name:
        return department_name
    if department_code:
        return "系所代碼{0}".format(department_code)
    return "未知系所"


def infer_department_aliases(
    department_name: str | None,
    department_code: str | None,
) -> list[str]:
    aliases: list[str] = []
    if department_name and "資訊工程" in department_name:
        aliases.extend(["資工系", "資工", "CSIE"])
    if department_name and "經濟" in department_name:
        aliases.extend(["經濟系", "經濟", "ECON"])
    if department_code:
        aliases.append(str(department_code))
    seen: set[str] = set()
    deduped: list[str] = []
    for alias in aliases:
        if alias not in seen:
            deduped.append(alias)
            seen.add(alias)
    return deduped
