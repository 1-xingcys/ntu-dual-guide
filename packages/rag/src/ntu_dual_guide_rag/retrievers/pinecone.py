from __future__ import annotations

from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import query_vectors_pinecone
from ntu_dual_guide_rag.settings import RagSettings

from ntu_dual_guide_rag.retrievers.utils import build_chunk


class PineconeRetriever:
    def __init__(self, settings: RagSettings, *, name: str = "dense-pinecone") -> None:
        self.settings = settings
        self.name = name

    def retrieve(self, question: str):
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
        chunks = []
        for item in response.get("matches", []):
            metadata = item.get("metadata") or {}
            score = float(item.get("score", 0.0))
            if score < self.settings.min_score:
                continue
            chunks.append(build_chunk(item.get("id", ""), score, metadata))
        return chunks

