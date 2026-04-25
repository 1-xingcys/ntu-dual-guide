from __future__ import annotations

from ntu_dual_guide_ingestion.chunkers.base import BaseGoldChunker
from ntu_dual_guide_ingestion.gold_schema import GoldChunk
from ntu_dual_guide_ingestion.gold_schema import GoldDocument


class SectionedSourceGoldChunker(BaseGoldChunker):
    chunker_name = "sectioned_source_chunker"
    chunker_version = "v1"

    def build_document(self, silver_document: dict) -> dict:
        chunks: list[GoldChunk] = []
        for section in silver_document["content"]["sections"]:
            order = len(chunks) + 1
            chunks.append(
                GoldChunk(
                    chunk_id="{0}-{1}".format(
                        silver_document["source_id"], section["section_id"]
                    ),
                    chunk_type="section",
                    title=section["heading"],
                    text="{0}\n{1}".format(section["heading"], section["body"]),
                    order=order,
                    metadata=self.scoped_metadata(
                        silver_document,
                        {
                            "section_id": section["section_id"],
                            "heading": section["heading"],
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
