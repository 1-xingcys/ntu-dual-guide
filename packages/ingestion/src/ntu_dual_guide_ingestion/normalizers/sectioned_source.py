from __future__ import annotations

import re
from typing import Any

from ntu_dual_guide_ingestion.normalizers.base import BaseSilverNormalizer
from ntu_dual_guide_ingestion.silver_schema import SectionedContent
from ntu_dual_guide_ingestion.silver_schema import SectionedSection
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import normalize_fragment


class BronzeSectionedSourceNormalizer(BaseSilverNormalizer):
    normalizer_name = "bronze_sectioned_source_normalizer"
    normalizer_version = "v1"

    def __init__(self, doc_type: str, source_id: str, authority_level: str = "secondary") -> None:
        self.doc_type = doc_type
        self.source_id = source_id
        self.authority_level = authority_level

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        sections = build_sectioned_content(bronze_document, self.doc_type)
        document = SilverDocument(
            dataset_version=bronze_document["dataset_version"],
            source_id=self.source_id,
            doc_type=self.doc_type,
            title=bronze_document["content"].get("title") or bronze_document["file_name"],
            source_path=bronze_document["raw_path"],
            source_hash=bronze_document["source_hash"],
            parser_name=bronze_document["parser_name"],
            parser_version=bronze_document["parser_version"],
            normalizer_version=self.normalizer_version,
            processing_fingerprint=self.processing_fingerprint(
                bronze_document["processing_fingerprint"]
            ),
            authority_level=self.authority_level,
            content=SectionedContent(sections=sections),
            source_url=bronze_document.get("source_url"),
        )
        return document.to_dict()


def build_sectioned_content(bronze_document: dict[str, Any], doc_type: str) -> list[SectionedSection]:
    blocks = bronze_document["content"]["blocks"]
    filter_fn = select_filter(doc_type)
    sections: list[SectionedSection] = []
    current_heading = bronze_document["content"].get("title") or bronze_document["file_name"]
    body_parts: list[str] = []

    def flush_section() -> None:
        body = normalize_fragment(" ".join(body_parts))
        if not body:
            return
        sections.append(
            SectionedSection(
                section_id="section-{0:03d}".format(len(sections) + 1),
                heading=current_heading,
                body=body,
            )
        )

    for block in blocks[1:]:
        text = normalize_fragment(block["text"])
        if not text or not filter_fn(text, block["block_type"]):
            continue
        if is_section_heading(text, block["block_type"], doc_type):
            flush_section()
            current_heading = text
            body_parts = []
            continue
        body_parts.append(text)

    flush_section()
    return sections


def select_filter(doc_type: str):
    if doc_type == "econ_portal_page":
        return is_econ_portal_content
    if doc_type == "ntu_policy_info_page":
        return is_policy_info_content
    return lambda text, block_type: True


def is_meaningful_heading(text: str) -> bool:
    if len(text) <= 1:
        return False
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return False
    return True


def is_section_heading(text: str, block_type: str, doc_type: str) -> bool:
    if doc_type == "econ_portal_page":
        return is_econ_portal_heading(text, block_type)
    return block_type == "heading" and is_meaningful_heading(text)


def is_econ_portal_content(text: str, block_type: str) -> bool:
    keywords = (
        "雙主修",
        "輔系",
        "轉雙輔",
        "轉系",
        "替代科目",
        "經濟系",
        "各系所必修課程查詢",
        "Q&A",
        "學分",
    )
    return any(keyword in text for keyword in keywords)


def is_econ_portal_heading(text: str, block_type: str) -> bool:
    heading_keywords = (
        "轉系、雙主修、輔系",
        "雙主修.輔系與轉系生替代科目說明",
        "雙主修&輔系常見Q&A",
        "輔系替代科目一覽表",
        "雙主修替代科目一覽表",
        "轉系生替代科目一覽表",
    )
    return any(keyword in text for keyword in heading_keywords)


def is_policy_info_content(text: str, block_type: str) -> bool:
    keywords = (
        "雙主修",
        "輔系",
        "轉系",
        "必修課程查詢",
        "應修學分數",
        "申請書",
        "畢業資格",
    )
    return any(keyword in text for keyword in keywords)
