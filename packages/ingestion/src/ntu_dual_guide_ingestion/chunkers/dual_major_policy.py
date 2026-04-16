from __future__ import annotations

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class DualMajorPolicyGoldChunker(BaseGoldChunker):
    chunker_name = "dual_major_policy_chunker"
    chunker_version = "v2"

    def build_document(self, silver_document: dict) -> dict:
        content = silver_document["content"]
        chunks: list[GoldChunk] = []
        academic_year = content.get("academic_year") or ""
        department_name = content.get("department_name") or ""
        context_prefix = build_policy_context_prefix(
            academic_year=academic_year,
            department_name=department_name,
        )

        overview_text = (
            "{context_prefix}。"
            "招收名額：{quota}。查詢電話：{contact_phone}。"
        ).format(
            context_prefix=context_prefix,
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
                    text="{0}規定，{1}：{2}".format(
                        context_prefix,
                        section["label"],
                        section["text"],
                    ),
                    order=order,
                    metadata={
                        "section_id": section["section_id"],
                        "section_label": section["label"],
                        "academic_year": academic_year or None,
                        "department_name": department_name or None,
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


def build_policy_context_prefix(*, academic_year: str, department_name: str) -> str:
    aliases = build_department_aliases(department_name)
    if aliases:
        return "{0}（{1}）{2}學年度雙主修相關規定".format(
            department_name,
            "、".join(aliases),
            academic_year,
        )
    if academic_year and department_name:
        return "{0}{1}學年度雙主修相關規定".format(department_name, academic_year)
    return "{0}雙主修相關規定".format(department_name or "")


def build_department_aliases(department_name: str) -> list[str]:
    if department_name == "經濟學系":
        return ["經濟系", "經濟", "ECON", "3030"]
    if department_name == "資訊工程學系":
        return ["資工系", "資工", "CSIE", "9020"]
    aliases: list[str] = []
    if department_name.endswith("學系"):
        short_name = department_name[:-2]
        aliases.append(short_name)
        if short_name.endswith("工程"):
            aliases.append(short_name.replace("工程", "工"))
    elif department_name:
        aliases.append(department_name)
    return aliases
