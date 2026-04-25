from __future__ import annotations

from pathlib import Path

from ntu_dual_guide_rag.models import RetrievalChunk

from ntu_dual_guide_rag.retrievers.protocol import Retriever
from ntu_dual_guide_rag.retrievers.utils import RelatedChunkIndex
from ntu_dual_guide_rag.retrievers.utils import replace_chunk_metadata
from ntu_dual_guide_rag.retrievers.utils import replace_chunk_score


class PromotedRetriever:
    """Post-process a base retriever with deterministic related-chunk promotion."""

    def __init__(
        self,
        base_retriever: Retriever,
        *,
        repo_root: Path,
        dataset_version: str,
        top_k: int,
        name: str = "promoted",
        relation_boost: float = 0.97,
        query_boost: float = 0.01,
    ) -> None:
        self.base_retriever = base_retriever
        self.top_k = top_k
        self.name = name
        self.relation_boost = relation_boost
        self.query_boost = query_boost
        self.related = RelatedChunkIndex.from_dataset(repo_root, dataset_version)

    def retrieve(self, question: str) -> list[RetrievalChunk]:
        chunks = self.base_retriever.retrieve(question)
        if not chunks:
            return []

        chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
        scores = {chunk.chunk_id: chunk.score for chunk in chunks}
        origin_rank = {chunk.chunk_id: float(rank) for rank, chunk in enumerate(chunks, start=1)}
        max_score = max(scores.values()) if scores else 0.0

        for chunk in chunks:
            for related_id in self.related.related_ids_for(chunk):
                promoted_score = chunk.score * self.relation_boost
                existing_score = scores.get(related_id)
                if existing_score is not None and existing_score >= promoted_score:
                    continue
                related_chunk = self.related.build_chunk(related_id, promoted_score)
                if related_chunk is None:
                    continue
                metadata = dict(related_chunk.metadata)
                metadata["promotion_reason"] = "related_chunk"
                metadata["promoted_from_chunk_id"] = chunk.chunk_id
                chunk_map[related_id] = replace_chunk_metadata(related_chunk, metadata)
                scores[related_id] = promoted_score
                origin_rank.setdefault(related_id, origin_rank[chunk.chunk_id] + 0.1)

        for offset, query_related_id in enumerate(self.related.query_related_ids(question)):
            boosted_score = max_score + self.query_boost - (offset * 0.0001)
            existing = chunk_map.get(query_related_id)
            if existing is not None:
                metadata = dict(existing.metadata)
                metadata["promotion_reason"] = "query_metadata_boost"
                chunk_map[query_related_id] = replace_chunk_metadata(existing, metadata)
                scores[query_related_id] = max(scores[query_related_id], boosted_score)
                continue
            related_chunk = self.related.build_chunk(query_related_id, boosted_score)
            if related_chunk is None:
                continue
            metadata = dict(related_chunk.metadata)
            metadata["promotion_reason"] = "query_metadata_boost"
            chunk_map[query_related_id] = replace_chunk_metadata(related_chunk, metadata)
            scores[query_related_id] = boosted_score
            origin_rank[query_related_id] = 0.5 + offset / 1000

        ranked_ids = sorted(
            chunk_map,
            key=lambda chunk_id: (scores[chunk_id], -origin_rank.get(chunk_id, 9999.0)),
            reverse=True,
        )
        return [
            replace_chunk_score(chunk_map[chunk_id], scores[chunk_id])
            for chunk_id in ranked_ids[: self.top_k]
        ]

