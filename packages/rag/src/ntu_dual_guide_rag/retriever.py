from __future__ import annotations

from typing import Protocol, runtime_checkable

from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import query_vectors_pinecone
from ntu_dual_guide_rag.models import RetrievalChunk
from ntu_dual_guide_rag.settings import RagSettings


@runtime_checkable
class Retriever(Protocol):
    """Common contract for all retriever implementations.

    The eval runner depends only on this protocol so that dense, hybrid,
    filtered, reranked, and decomposing retrievers can all be swapped in.
    """

    name: str

    def retrieve(self, question: str) -> list[RetrievalChunk]: ...


class PineconeRetriever:
    def __init__(self, settings: RagSettings, *, name: str = "dense-pinecone") -> None:
        self.settings = settings
        self.name = name

    def retrieve(self, question: str) -> list[RetrievalChunk]:
        query_vector = embed_texts_openai(
            [question],
            model=self.settings.openai_embedding_model,
            api_key=self.settings.openai_api_key,
        )[0]
        response = query_vectors_pinecone(
            query_vector,
            namespace=self.settings.namespace,
            index_host=self.settings.pinecone_index_host,
            api_key=self.settings.pinecone_api_key,
            top_k=self.settings.top_k,
            api_version=self.settings.pinecone_api_version,
        )
        chunks: list[RetrievalChunk] = []
        for item in response.get("matches", []):
            metadata = item.get("metadata") or {}
            score = float(item.get("score", 0.0))
            if score < self.settings.min_score:
                continue
            chunks.append(
                RetrievalChunk(
                    chunk_id=item.get("id", ""),
                    score=score,
                    source_id=metadata.get("source_id", ""),
                    doc_type=metadata.get("doc_type", ""),
                    chunk_type=metadata.get("chunk_type", ""),
                    title=metadata.get("chunk_title") or metadata.get("title") or "",
                    text=metadata.get("chunk_text", ""),
                    metadata=metadata,
                )
            )
        return chunks
