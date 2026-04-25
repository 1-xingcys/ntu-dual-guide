from __future__ import annotations

from typing import Any

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class FaqGoldChunker(BaseGoldChunker):
    chunker_name = "faq_chunker"
    chunker_version = "v1"

    def build_document(self, silver_document: dict[str, Any]) -> dict[str, Any]:
        chunks: list[GoldChunk] = []
        for qa_pair in silver_document["content"]["qa_pairs"]:
            order = len(chunks) + 1
            chunks.append(
                GoldChunk(
                    chunk_id=qa_pair["qa_id"],
                    chunk_type="faq_qa",
                    title=qa_pair["question"],
                    text="問題：{0}\n答案：{1}".format(
                        qa_pair["question"], qa_pair["answer"]
                    ),
                    order=order,
                    metadata=self.scoped_metadata(
                        silver_document,
                        {
                            "question": qa_pair["question"],
                            "topics": qa_pair.get("topics", []),
                        },
                    ),
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
            authority_level=silver_document.get("authority_level", "secondary"),
        )
        return document.to_dict()
