from __future__ import annotations

from pathlib import Path

from ntu_dual_guide_rag.models import ChatAnswer
from ntu_dual_guide_rag.models import Citation
from ntu_dual_guide_rag.openai_responses import create_text_response
from ntu_dual_guide_rag.prompts import SYSTEM_PROMPT
from ntu_dual_guide_rag.prompts import build_user_prompt
from ntu_dual_guide_rag.retriever import PineconeRetriever
from ntu_dual_guide_rag.settings import RagSettings


class RagService:
    def __init__(self, settings: RagSettings) -> None:
        self.settings = settings
        self.retriever = PineconeRetriever(settings)

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "RagService":
        settings = RagSettings.from_env(repo_root)
        return cls(settings)

    def answer(self, question: str) -> ChatAnswer:
        retrieved_chunks = self.retriever.retrieve(question)
        if not retrieved_chunks:
            return self._unknown_answer([])

        prompt = build_user_prompt(question, retrieved_chunks)
        answer_text = create_text_response(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            user_input=prompt,
        ).strip()

        if not answer_text or answer_text == "不知道":
            return self._unknown_answer(retrieved_chunks)

        citations = build_citations(retrieved_chunks[:3])
        return ChatAnswer(
            answer=answer_text,
            status="answered",
            model=self.settings.openai_model,
            dataset_version=self.settings.dataset_version,
            namespace=self.settings.namespace,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
        )

    def _unknown_answer(self, retrieved_chunks) -> ChatAnswer:
        return ChatAnswer(
            answer="不知道",
            status="unknown",
            model=self.settings.openai_model,
            dataset_version=self.settings.dataset_version,
            namespace=self.settings.namespace,
            citations=build_citations(retrieved_chunks[:3]),
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
