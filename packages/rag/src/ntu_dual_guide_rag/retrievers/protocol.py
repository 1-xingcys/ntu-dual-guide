from __future__ import annotations

from typing import Protocol, runtime_checkable

from ntu_dual_guide_rag.models import RetrievalChunk


@runtime_checkable
class Retriever(Protocol):
    """Common contract for all retriever implementations."""

    name: str

    def retrieve(self, question: str) -> list[RetrievalChunk]: ...

