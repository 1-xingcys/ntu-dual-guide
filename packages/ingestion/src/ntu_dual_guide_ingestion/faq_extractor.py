from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ntu_dual_guide_ingestion.silver_schema import FaqContent
from ntu_dual_guide_ingestion.silver_schema import FaqQAPair
from ntu_dual_guide_ingestion.silver_schema import SilverDocument

PARSER_NAME = "pdftotext"
PARSER_VERSION = "v1"
NORMALIZER_VERSION = "v1"


@dataclass
class QAPair:
    qa_id: str
    question: str
    answer: str
    topics: list[str]

    def to_schema(self) -> FaqQAPair:
        return FaqQAPair(
            qa_id=self.qa_id,
            question=self.question,
            answer=self.answer,
            topics=self.topics,
        )


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def normalize_whitespace(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = text.replace("\u3000", " ")
    text = text.replace("：", ": ")
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return text.strip()


def normalize_fragment(text: str) -> str:
    text = normalize_whitespace(text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(text: str, fallback: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else fallback


def infer_topics(question: str, answer: str) -> list[str]:
    haystack = f"{question} {answer}"
    keyword_topics = [
        ("學分要求", ["學分", "修完", "取得學位"]),
        ("兼充", ["兼充", "一修二用"]),
        ("課程認列", ["計入", "替代", "課名相同"]),
        ("統計課程", ["統計學", "計量經濟學"]),
        ("雙主修", ["雙主修"]),
        ("輔系", ["輔系"]),
        ("核准年度", ["核准年度"]),
    ]
    topics: list[str] = []
    for topic, keywords in keyword_topics:
        if any(keyword in haystack for keyword in keywords):
            topics.append(topic)
    return topics


def split_qa_pairs(text: str, source_id: str) -> list[QAPair]:
    pattern = re.compile(r"Q[:：]\s*(.+?)\nA[:：]\s*(.+?)(?=\nQ[:：]|\Z)", re.S)
    pairs: list[QAPair] = []
    for index, match in enumerate(pattern.finditer(text), start=1):
        question = normalize_fragment(match.group(1))
        answer = normalize_fragment(match.group(2))
        if not question or not answer:
            continue
        qa_id = f"{source_id}-q{index}"
        pairs.append(
            QAPair(
                qa_id=qa_id,
                question=question,
                answer=answer,
                topics=infer_topics(question, answer),
            )
        )
    return pairs


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def processing_fingerprint(source_hash: str) -> str:
    payload = f"{source_hash}|{PARSER_NAME}|{PARSER_VERSION}|{NORMALIZER_VERSION}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_output(pdf_path: Path, source_id: str) -> dict[str, object]:
    raw_text = extract_pdf_text(pdf_path)
    normalized_text = normalize_whitespace(raw_text)
    source_hash = sha256_file(pdf_path)

    document = SilverDocument(
        source_id=source_id,
        doc_type="faq",
        title=extract_title(normalized_text, pdf_path.stem),
        source_path=str(pdf_path),
        source_hash=source_hash,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
        processing_fingerprint=processing_fingerprint(source_hash),
        content=FaqContent(
            qa_pairs=[pair.to_schema() for pair in split_qa_pairs(normalized_text, source_id)]
        ),
    )
    return document.to_dict()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract FAQ Q/A pairs from a PDF.")
    parser.add_argument("input_pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument("output_json", type=Path, help="Path to write normalized JSON.")
    parser.add_argument(
        "--source-id",
        default="econ-dual-major-faq",
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
