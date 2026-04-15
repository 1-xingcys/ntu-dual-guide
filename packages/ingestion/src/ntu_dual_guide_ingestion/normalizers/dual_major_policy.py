from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ntu_dual_guide_ingestion.normalizers.base import BaseSilverNormalizer
from ntu_dual_guide_ingestion.silver_schema import DualMajorPolicyContent
from ntu_dual_guide_ingestion.silver_schema import DualMajorPolicySection
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import normalize_fragment


SECTION_SPECS = [
    ("eligibility", "申請資格"),
    ("selection_method_and_weight", "錄取方式及占分比例"),
    ("other", "其他"),
    ("notes", "備註"),
]


@dataclass
class ParsedPolicy:
    title: str
    academic_year: str | None
    department_name: str | None
    quota: str | None
    contact_phone: str | None
    sections: list[DualMajorPolicySection]


class BronzeDualMajorPolicyNormalizer(BaseSilverNormalizer):
    normalizer_name = "bronze_dual_major_policy_normalizer"
    normalizer_version = "v1"

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_policy_from_bronze(bronze_document)
        source_id = infer_policy_source_id(bronze_document, parsed)
        document = SilverDocument(
            source_id=source_id,
            doc_type="dual_major_policy",
            title=parsed.title,
            source_path=bronze_document["raw_path"],
            source_hash=bronze_document["source_hash"],
            parser_name=bronze_document["parser_name"],
            parser_version=bronze_document["parser_version"],
            normalizer_version=self.normalizer_version,
            processing_fingerprint=self.processing_fingerprint(
                bronze_document["processing_fingerprint"]
            ),
            authority_level="primary",
            content=DualMajorPolicyContent(
                academic_year=parsed.academic_year,
                department_name=parsed.department_name,
                quota=parsed.quota,
                contact_phone=parsed.contact_phone,
                sections=parsed.sections,
            ),
            source_url=bronze_document.get("source_url"),
        )
        return document.to_dict()


def infer_policy_source_id(bronze_document: dict[str, Any], parsed: ParsedPolicy) -> str:
    department_slug = "department"
    if parsed.department_name:
        if "經濟" in parsed.department_name:
            department_slug = "econ"
        else:
            department_slug = parsed.department_name.lower().replace("學系", "").replace("系", "")
    year = parsed.academic_year or "unknown"
    return "{0}-dual-major-policy-{1}".format(department_slug, year)


def parse_policy_from_bronze(bronze_document: dict[str, Any]) -> ParsedPolicy:
    blocks = bronze_document["content"]["blocks"]
    title = bronze_document["content"].get("title") or bronze_document["file_name"]
    academic_year = extract_academic_year(title)
    department_name = None
    quota = None
    contact_phone = None
    sections = {section_id: [] for section_id, _ in SECTION_SPECS}
    current_section = None
    pre_section_lines: list[str] = []

    for block in blocks[1:]:
        text = normalize_fragment(block["text"])
        if not text:
            continue
        if text.startswith("系所名稱"):
            department_name = normalize_fragment(text.replace("系所名稱", "", 1))
            continue
        if text.startswith("招收名額"):
            quota = normalize_fragment(text.replace("招收名額", "", 1))
            continue
        if text.startswith("查詢電話"):
            contact_phone = normalize_fragment(text.replace("查詢電話", "", 1))
            continue

        if text.startswith("申請資格"):
            current_section = "eligibility"
            sections[current_section].extend(pre_section_lines)
            pre_section_lines = []
            remainder = normalize_fragment(text.replace("申請資格", "", 1))
            if remainder:
                sections[current_section].append(remainder)
            continue

        if text.startswith("錄取方式及"):
            current_section = "selection_method_and_weight"
            remainder = normalize_fragment(text.replace("錄取方式及", "", 1))
            if remainder:
                sections[current_section].append(remainder)
            continue

        if text.startswith("其他"):
            current_section = "other"
            remainder = normalize_fragment(text.replace("其他", "", 1))
            if remainder:
                sections[current_section].append(remainder)
            continue

        if "備註" in text:
            before, _, after = text.partition("備註")
            if before and current_section:
                sections[current_section].append(before)
            current_section = "notes"
            remainder = normalize_fragment(after)
            if remainder:
                sections[current_section].append(remainder)
            continue

        if current_section:
            sections[current_section].append(text)
        else:
            pre_section_lines.append(text)

    if pre_section_lines:
        sections["eligibility"] = pre_section_lines + sections["eligibility"]

    sections = rebalance_policy_sections(sections)
    section_models = [
        DualMajorPolicySection(
            section_id=section_id,
            label=label,
            text=cleanup_policy_text(section_id, sections[section_id]),
        )
        for section_id, label in SECTION_SPECS
        if cleanup_policy_text(section_id, sections[section_id])
    ]

    return ParsedPolicy(
        title=title,
        academic_year=academic_year,
        department_name=department_name,
        quota=quota,
        contact_phone=contact_phone,
        sections=section_models,
    )


def cleanup_policy_text(section_id: str, lines: list[str]) -> str:
    text = normalize_fragment(" ".join(lines))
    if section_id == "selection_method_and_weight":
        text = re.sub(r"^錄取方式[:：]?", "錄取方式: ", text)
        text = re.sub(r"雙占分比例", "雙主修", text)
        text = re.sub(r"錄取方式:\s*錄取方式", "錄取方式", text)
        text = re.sub(r"雙主修主修", "雙主修", text)
        text = re.sub(r"雙主修主修必修", "雙主修必修", text)
        text = re.sub(r"\s+", " ", text)
    return text


def rebalance_policy_sections(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    other_text = normalize_fragment(" ".join(sections["other"]))
    if other_text.startswith("無") and len(other_text) > 1:
        trailing = normalize_fragment(other_text[1:])
        sections["other"] = ["無"]
        if trailing:
            sections["notes"] = [trailing] + sections["notes"]
    return sections


def extract_academic_year(title: str) -> str | None:
    match = re.search(r"(\d+)學年度", title)
    return match.group(1) if match else None
