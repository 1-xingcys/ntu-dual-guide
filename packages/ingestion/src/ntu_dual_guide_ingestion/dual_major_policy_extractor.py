from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ntu_dual_guide_ingestion.silver_schema import DualMajorPolicyContent
from ntu_dual_guide_ingestion.silver_schema import DualMajorPolicySection
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import extract_pdf_text
from ntu_dual_guide_ingestion.utils import extract_title
from ntu_dual_guide_ingestion.utils import normalize_fragment
from ntu_dual_guide_ingestion.utils import normalize_whitespace
from ntu_dual_guide_ingestion.utils import sha256_file


PARSER_NAME = "pdftotext-layout"
PARSER_VERSION = "v1"
NORMALIZER_VERSION = "v1"


SECTION_SPECS = [
    ("eligibility", "申請資格"),
    ("selection_method_and_weight", "錄取方式及占分比例"),
    ("other", "其他"),
    ("notes", "備註"),
]
TERMINAL_LABELS = {"查詢電話"}
LINE_LABEL_PATTERNS = [
    ("department_name", re.compile(r"^系所名稱\s+(?P<value>.+)$")),
    ("quota", re.compile(r"^招收名額\s+(?P<value>.+)$")),
    ("contact_phone", re.compile(r"^查詢電話\s+(?P<value>.+)$")),
    ("eligibility", re.compile(r"^申請資格\s*(?P<value>.*)$")),
    ("selection_method_and_weight", re.compile(r"^錄取方式及\s*(?P<value>.*)$")),
    ("other", re.compile(r"^其他\s*(?P<value>.*)$")),
    ("notes", re.compile(r"^備註\s*(?P<value>.*)$")),
]
LABEL_ALIASES = {
    "department_name": "系所名稱",
    "quota": "招收名額",
    "contact_phone": "查詢電話",
    "eligibility": "申請資格",
    "selection_method_and_weight": "錄取方式及占分比例",
    "other": "其他",
    "notes": "備註",
}
SECTION_IDS = {section_id for section_id, _ in SECTION_SPECS}


@dataclass
class ParsedPolicy:
    title: str
    academic_year: str | None
    department_name: str | None
    quota: str | None
    contact_phone: str | None
    sections: list[DualMajorPolicySection]


def processing_fingerprint(source_hash: str) -> str:
    payload = f"{source_hash}|{PARSER_NAME}|{PARSER_VERSION}|{NORMALIZER_VERSION}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def extract_academic_year(title: str) -> str | None:
    match = re.search(r"(\d+)學年度", title)
    return match.group(1) if match else None


def cleanup_section_text(section_id: str, text: str) -> str:
    text = normalize_fragment(text)
    if section_id == "selection_method_and_weight":
        text = re.sub(r"^占分比例\s+", "", text)
        text = re.sub(r"占分比例\s+(?![:：0-9])", "", text)
        text = re.sub(r"(?<=\S)\s+占分比例\s+(?=\S)", " ", text)
    return text


def rebalance_sections(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    if sections["other"]:
        other_text = cleanup_section_text("other", " ".join(sections["other"]))
        match = re.match(r"^無\s+(.+)$", other_text)
        if match:
            trailing_text = match.group(1).strip()
            sections["other"] = ["無"]
            if trailing_text:
                existing_notes = cleanup_section_text("notes", " ".join(sections["notes"]))
                if existing_notes:
                    if " 2." in existing_notes:
                        existing_notes = existing_notes.replace(
                            " 2.",
                            f" {trailing_text} 2.",
                            1,
                        )
                    else:
                        existing_notes = f"{trailing_text} {existing_notes}"
                    sections["notes"] = [existing_notes]
                else:
                    sections["notes"] = [trailing_text]
    return sections


def parse_policy(text: str, fallback_title: str) -> ParsedPolicy:
    normalized_text = normalize_whitespace(text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    title = extract_title(normalized_text, fallback_title)
    academic_year = extract_academic_year(title)

    department_name: str | None = None
    quota: str | None = None
    contact_phone: str | None = None
    sections: dict[str, list[str]] = {section_id: [] for section_id, _ in SECTION_SPECS}

    current_section: str | None = None
    pending_leading_lines: list[str] = []
    pending_note_lines: list[str] = []
    seen_first_section = False

    for line in lines[1:]:
        matched = False
        for field_id, pattern in LINE_LABEL_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            value = normalize_fragment(match.group("value"))
            matched = True

            if field_id == "department_name":
                department_name = value or None
                current_section = None
            elif field_id == "quota":
                quota = value or None
                current_section = None
            elif field_id == "contact_phone":
                contact_phone = value or None
                current_section = None
            elif field_id in SECTION_IDS:
                current_section = field_id
                seen_first_section = True
                if field_id == "eligibility" and pending_leading_lines:
                    sections[field_id].extend(pending_leading_lines)
                    pending_leading_lines = []
                if field_id == "notes" and pending_note_lines:
                    sections[field_id].extend(pending_note_lines)
                    pending_note_lines = []
                if value:
                    sections[field_id].append(value)
            break

        if matched:
            continue

        if current_section:
            if current_section == "other" and sections["other"] == ["無"]:
                pending_note_lines.append(line)
                continue
            sections[current_section].append(line)
        else:
            if not seen_first_section:
                pending_leading_lines.append(line)

    if pending_leading_lines and not sections["eligibility"]:
        sections["eligibility"] = pending_leading_lines + sections["eligibility"]

    if pending_note_lines:
        sections["notes"] = pending_note_lines + sections["notes"]

    sections = rebalance_sections(sections)

    section_models = [
        DualMajorPolicySection(
            section_id=section_id,
            label=label,
            text=cleanup_section_text(section_id, " ".join(sections[section_id])),
        )
        for section_id, label in SECTION_SPECS
        if cleanup_section_text(section_id, " ".join(sections[section_id]))
    ]

    return ParsedPolicy(
        title=title,
        academic_year=academic_year,
        department_name=department_name,
        quota=quota,
        contact_phone=contact_phone,
        sections=section_models,
    )


def build_output(pdf_path: Path, source_id: str) -> dict[str, object]:
    raw_text = extract_pdf_text(pdf_path, layout=True)
    source_hash = sha256_file(pdf_path)
    policy = parse_policy(raw_text, pdf_path.stem)

    document = SilverDocument(
        source_id=source_id,
        doc_type="dual_major_policy",
        title=policy.title,
        source_path=str(pdf_path),
        source_hash=source_hash,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        processing_fingerprint=processing_fingerprint(source_hash),
        authority_level="primary",
        content=DualMajorPolicyContent(
            academic_year=policy.academic_year,
            department_name=policy.department_name,
            quota=policy.quota,
            contact_phone=policy.contact_phone,
            sections=policy.sections,
        ),
    )
    return document.to_dict()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract NTU departmental dual-major policy PDFs into silver JSON."
    )
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument("output_json", type=Path, help="Path to write normalized JSON.")
    parser.add_argument(
        "--source-id",
        default="ntu-department-dual-major-policy",
        help="Stable source identifier for the extracted document.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_output(args.input_pdf, args.source_id)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
