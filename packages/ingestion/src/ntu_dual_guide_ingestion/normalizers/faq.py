from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ntu_dual_guide_ingestion.faq_extractor import infer_topics
from ntu_dual_guide_ingestion.normalizers.base import BaseSilverNormalizer
from ntu_dual_guide_ingestion.silver_schema import FaqContent
from ntu_dual_guide_ingestion.silver_schema import FaqQAPair
from ntu_dual_guide_ingestion.silver_schema import SilverDocument
from ntu_dual_guide_ingestion.utils import normalize_fragment


@dataclass
class PendingQA:
    question: str | None = None
    answer_parts: list[str] | None = None

    def __post_init__(self) -> None:
        if self.answer_parts is None:
            self.answer_parts = []


class BronzeFaqNormalizer(BaseSilverNormalizer):
    normalizer_name = "bronze_faq_normalizer"
    normalizer_version = "v1"

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        source_id = infer_faq_source_id(bronze_document)
        qa_pairs = extract_qa_pairs(bronze_document, source_id)
        document = SilverDocument(
            source_id=source_id,
            doc_type="faq",
            title=bronze_document["content"].get("title") or bronze_document["file_name"],
            source_path=bronze_document["raw_path"],
            source_hash=bronze_document["source_hash"],
            parser_name=bronze_document["parser_name"],
            parser_version=bronze_document["parser_version"],
            normalizer_version=self.normalizer_version,
            processing_fingerprint=self.processing_fingerprint(
                bronze_document["processing_fingerprint"]
            ),
            content=FaqContent(qa_pairs=qa_pairs),
            source_url=bronze_document.get("source_url"),
        )
        return document.to_dict()


def infer_faq_source_id(bronze_document: dict[str, Any]) -> str:
    file_name = bronze_document["file_name"]
    if "台大經濟雙主修_輔系常見Q_A" in file_name or "常見 Q&A" in bronze_document["content"].get(
        "title", ""
    ):
        return "econ-dual-major-faq"
    stem = file_name.rsplit(".", 1)[0]
    return stem.lower().replace(" ", "-")


def extract_qa_pairs(bronze_document: dict[str, Any], source_id: str) -> list[FaqQAPair]:
    blocks = bronze_document["content"]["blocks"]
    pairs: list[FaqQAPair] = []
    pending = PendingQA()

    def flush_pair() -> None:
        if not pending.question or not pending.answer_parts:
            return
        answer = normalize_fragment(" ".join(pending.answer_parts))
        if not answer:
            return
        qa_id = "{0}-q{1}".format(source_id, len(pairs) + 1)
        pairs.append(
            FaqQAPair(
                qa_id=qa_id,
                question=pending.question,
                answer=answer,
                topics=infer_topics(pending.question, answer),
            )
        )
        pending.question = None
        pending.answer_parts = []

    for block in blocks:
        text = normalize_fragment(block["text"])
        if not text:
            continue
        if text.startswith("Q:"):
            flush_pair()
            pending.question = normalize_fragment(text[2:].lstrip(" :："))
            pending.answer_parts = []
            continue
        if text.startswith("A:"):
            pending.answer_parts.append(normalize_fragment(text[2:].lstrip(" :：")))
            continue
        if pending.answer_parts:
            pending.answer_parts.append(text)

    flush_pair()
    return pairs
