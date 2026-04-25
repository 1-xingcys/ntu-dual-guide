from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from ntu_dual_guide_rag.models import ChatAnswer
from ntu_dual_guide_rag.models import Citation
from ntu_dual_guide_rag.openai_responses import create_text_response
from ntu_dual_guide_rag.openai_responses import stream_text_response
from ntu_dual_guide_rag.prompts import SYSTEM_PROMPT
from ntu_dual_guide_rag.prompts import build_user_prompt
from ntu_dual_guide_rag.retrievers import Retriever
from ntu_dual_guide_rag.retrievers import build_retriever
from ntu_dual_guide_rag.settings import RagSettings


class RagService:
    def __init__(
        self,
        settings: RagSettings,
        *,
        retriever: Retriever,
        generate_on_empty_retrieval: bool = False,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.generate_on_empty_retrieval = generate_on_empty_retrieval

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "RagService":
        settings = RagSettings.from_env(repo_root)
        retriever = build_retriever(
            settings.retriever,
            settings=settings,
            repo_root=repo_root,
            top_k=settings.top_k,
            dense_top_k=settings.dense_top_k,
            sparse_top_k=settings.sparse_top_k,
            dense_weight=settings.dense_weight,
            sparse_weight=settings.sparse_weight,
            rrf_k=settings.rrf_k,
        )
        return cls(settings, retriever=retriever)

    def answer(self, question: str) -> ChatAnswer:
        retrieved_chunks = self.retriever.retrieve(question)
        if not retrieved_chunks and not self.generate_on_empty_retrieval:
            return self._unknown_answer([])

        prompt = build_user_prompt(question, retrieved_chunks)
        answer = create_text_response(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            user_input=prompt,
        )
        return ChatAnswer(
            answer=answer.strip() or "不知道",
            status="answered" if retrieved_chunks else "unknown",
            model=self.settings.openai_model,
            dataset_version=self.settings.dataset_version,
            namespace=self.settings.namespace,
            citations=build_citations(retrieved_chunks),
            retrieved_chunks=retrieved_chunks,
        )

    def stream_answer(self, question: str) -> Iterator[tuple[str, Any]]:
        """Stream a RAG answer as a sequence of stage / token / final events.

        Event tuples (kind, payload):
          ("stage", "retrieving")
          ("retrieved", list[RetrievalChunk])
          ("stage", "generating")          # only if generation runs
          ("token", str)                    # delta chunks
          ("final", ChatAnswer)
        """
        yield ("stage", "retrieving")
        retrieved_chunks = self.retriever.retrieve(question)
        yield ("retrieved", retrieved_chunks)

        if not retrieved_chunks and not self.generate_on_empty_retrieval:
            yield ("final", self._unknown_answer([]))
            return

        prompt = build_user_prompt(question, retrieved_chunks)
        yield ("stage", "generating")

        buffer: list[str] = []
        for kind, text in stream_text_response(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            user_input=prompt,
        ):
            if kind == "delta":
                buffer.append(text)
                yield ("token", text)
            elif kind == "reasoning":
                yield ("reasoning", text)
            elif kind == "done" and not buffer:
                buffer.append(text)

        answer_text = "".join(buffer).strip() or "不知道"
        yield (
            "final",
            ChatAnswer(
                answer=answer_text,
                status="answered" if retrieved_chunks else "unknown",
                model=self.settings.openai_model,
                dataset_version=self.settings.dataset_version,
                namespace=self.settings.namespace,
                citations=build_citations(retrieved_chunks),
                retrieved_chunks=retrieved_chunks,
            ),
        )

    def _unknown_answer(self, retrieved_chunks, *, answer_text: str = "不知道") -> ChatAnswer:
        return ChatAnswer(
            answer=answer_text or "不知道",
            status="unknown",
            model=self.settings.openai_model,
            dataset_version=self.settings.dataset_version,
            namespace=self.settings.namespace,
            citations=build_citations(retrieved_chunks),
            retrieved_chunks=retrieved_chunks,
        )


def build_citations(retrieved_chunks) -> list[Citation]:
    citations: list[Citation] = []
    for index, chunk in enumerate(retrieved_chunks, start=1):
        citations.append(
            Citation(
                index=index,
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                title=chunk.metadata.get("title") or chunk.title,
                chunk_title=chunk.title,
                source_path=chunk.metadata.get("source_path"),
                score=chunk.score,
            )
        )
    return citations
