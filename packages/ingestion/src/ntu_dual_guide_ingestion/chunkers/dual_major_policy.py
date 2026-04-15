from __future__ import annotations

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class DualMajorPolicyGoldChunker(BaseGoldChunker):
    chunker_name = "dual_major_policy_chunker"
    chunker_version = "v1"

    def build_document(self, silver_document: dict) -> dict:
        content = silver_document["content"]
        chunks: list[GoldChunk] = []

        overview_text = (
            "{academic_year}學年度 {department_name} 雙主修規定。"
            "招收名額：{quota}。查詢電話：{contact_phone}。"
        ).format(
            academic_year=content.get("academic_year") or "",
            department_name=content.get("department_name") or "",
            quota=content.get("quota") or "未提供",
            contact_phone=content.get("contact_phone") or "未提供",
        ).strip()
        chunks.append(
            GoldChunk(
                chunk_id="{0}-overview".format(silver_document["source_id"]),
                chunk_type="policy_overview",
                title="{0} 概覽".format(silver_document["title"]),
                text=overview_text,
                order=1,
                metadata={
                    "academic_year": content.get("academic_year"),
                    "department_name": content.get("department_name"),
                    "quota": content.get("quota"),
                    "contact_phone": content.get("contact_phone"),
                },
            )
        )

        for section in content["sections"]:
            order = len(chunks) + 1
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-{1}".format(
                        silver_document["source_id"], section["section_id"]
                    ),
                    chunk_type="policy_section",
                    title=section["label"],
                    text="{0}\n{1}".format(section["label"], section["text"]),
                    order=order,
                    metadata={
                        "section_id": section["section_id"],
                        "section_label": section["label"],
                        "academic_year": content.get("academic_year"),
                        "department_name": content.get("department_name"),
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
