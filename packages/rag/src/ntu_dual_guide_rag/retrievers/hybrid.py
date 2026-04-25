from __future__ import annotations

from pathlib import Path

from ntu_dual_guide_rag.retrievers.bm25 import BM25Index
from ntu_dual_guide_rag.retrievers.bm25 import build_bm25_for_dataset
from ntu_dual_guide_rag.models import RetrievalChunk
from ntu_dual_guide_rag.settings import RagSettings

from ntu_dual_guide_rag.retrievers.pinecone import PineconeRetriever
from ntu_dual_guide_rag.retrievers.utils import build_chunk


class HybridRetriever:
    def __init__(
        self,
        settings: RagSettings,
        *,
        repo_root: Path,
        dense_top_k: int,
        sparse_top_k: int,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
        rrf_k: int = 60,
        name: str = "hybrid-rrf",
        bm25_index: BM25Index | None = None,
    ) -> None:
        self.settings = settings
        self.name = name
        self.dense_top_k = dense_top_k
        self.sparse_top_k = sparse_top_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k
        dense_settings = RagSettings(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_embedding_model=settings.openai_embedding_model,
            pinecone_api_key=settings.pinecone_api_key,
            pinecone_index_host=settings.pinecone_index_host,
            pinecone_api_version=settings.pinecone_api_version,
            dataset_version=settings.dataset_version,
            namespace=settings.namespace,
            top_k=dense_top_k,
            min_score=settings.min_score,
        )
        self.dense_retriever = PineconeRetriever(
            dense_settings,
            name="dense-pinecone-top{0}".format(dense_top_k),
        )
        self.bm25 = bm25_index or build_bm25_for_dataset(repo_root, settings.dataset_version)

    def retrieve(self, question: str) -> list[RetrievalChunk]:
        dense_chunks = self.dense_retriever.retrieve(question)
        sparse_hits = self.bm25.search(question, top_k=self.sparse_top_k)

        fused_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievalChunk] = {}

        for rank, chunk in enumerate(dense_chunks, start=1):
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + (
                self.dense_weight / (self.rrf_k + rank)
            )
            metadata = dict(chunk.metadata)
            metadata["dense_score"] = chunk.score
            chunk_map[chunk.chunk_id] = RetrievalChunk(
                chunk_id=chunk.chunk_id,
                score=chunk.score,
                source_id=chunk.source_id,
                doc_type=chunk.doc_type,
                chunk_type=chunk.chunk_type,
                title=chunk.title,
                text=chunk.text,
                metadata=metadata,
            )

        for rank, (chunk_id, sparse_score, metadata) in enumerate(sparse_hits, start=1):
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (
                self.sparse_weight / (self.rrf_k + rank)
            )
            existing = chunk_map.get(chunk_id)
            merged_metadata = dict(metadata)
            merged_metadata["sparse_score"] = sparse_score
            if existing is not None:
                existing.metadata.update({"sparse_score": sparse_score})
                continue
            chunk_map[chunk_id] = build_chunk(
                chunk_id,
                sparse_score,
                merged_metadata,
            )

        ranked_ids = sorted(
            fused_scores,
            key=lambda chunk_id: (fused_scores[chunk_id], chunk_map[chunk_id].score),
            reverse=True,
        )
        fused_chunks: list[RetrievalChunk] = []
        for chunk_id in ranked_ids[: self.settings.top_k]:
            chunk = chunk_map[chunk_id]
            metadata = dict(chunk.metadata)
            metadata["hybrid_score"] = fused_scores[chunk_id]
            fused_chunks.append(
                RetrievalChunk(
                    chunk_id=chunk.chunk_id,
                    score=fused_scores[chunk_id],
                    source_id=chunk.source_id,
                    doc_type=chunk.doc_type,
                    chunk_type=chunk.chunk_type,
                    title=chunk.title,
                    text=chunk.text,
                    metadata=metadata,
                )
            )
        return fused_chunks

