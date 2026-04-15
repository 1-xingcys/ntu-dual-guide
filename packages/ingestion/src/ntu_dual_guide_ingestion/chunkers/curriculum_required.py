from __future__ import annotations

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class CurriculumRequiredGoldChunker(BaseGoldChunker):
    chunker_name = "curriculum_required_chunker"
    chunker_version = "v1"

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
            order = len(chunks) + 1
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-note-{1:03d}".format(silver_document["source_id"], index),
                    chunk_type="curriculum_note",
                    title="規定說明 {0}".format(index),
                    text=note,
                    order=order,
                    metadata={
                        "department_code": content.get("department_code"),
                        "admission_year": content.get("admission_year"),
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
