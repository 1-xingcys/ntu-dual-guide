from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ntu_dual_guide_rag.retrievers.hybrid import HybridRetriever
from ntu_dual_guide_rag.retrievers.llm_decomposed import LlmDecomposedRetriever
from ntu_dual_guide_rag.retrievers.pinecone import PineconeRetriever
from ntu_dual_guide_rag.retrievers.promoted import PromotedRetriever
from ntu_dual_guide_rag.retrievers.protocol import Retriever
from ntu_dual_guide_rag.settings import RagSettings


RETRIEVER_CHOICES = ("dense", "hybrid", "hybrid_promoted", "llm_decomposed")


def build_retriever(
    name: str,
    *,
    settings: RagSettings,
    repo_root: Path,
    top_k: int | None = None,
    min_score: float | None = None,
    dense_top_k: int | None = None,
    sparse_top_k: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    rrf_k: int = 60,
) -> Retriever:
    final_settings = replace(
        settings,
        top_k=top_k if top_k is not None else settings.top_k,
        min_score=min_score if min_score is not None else settings.min_score,
    )
    final_dense_top_k = max(dense_top_k or final_settings.top_k, final_settings.top_k)
    final_sparse_top_k = max(sparse_top_k or final_settings.top_k, final_settings.top_k)

    if name == "dense":
        return PineconeRetriever(
            final_settings,
            name="dense-pinecone-top{0}".format(final_settings.top_k),
        )
    if name == "hybrid":
        return HybridRetriever(
            final_settings,
            repo_root=repo_root,
            dense_top_k=final_dense_top_k,
            sparse_top_k=final_sparse_top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            name=(
                "hybrid-rrf-dense{0}-sparse{1}-dw{2:g}-sw{3:g}-k{4}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
    if name == "hybrid_promoted":
        candidate_top_k = max(
            final_dense_top_k,
            final_sparse_top_k,
            final_settings.top_k,
        )
        candidate_settings = replace(final_settings, top_k=candidate_top_k)
        base_retriever = HybridRetriever(
            candidate_settings,
            repo_root=repo_root,
            dense_top_k=final_dense_top_k,
            sparse_top_k=final_sparse_top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            name=(
                "hybrid-rrf-dense{0}-sparse{1}-candidate{2}-dw{3:g}-sw{4:g}-k{5}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    candidate_top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
        return PromotedRetriever(
            base_retriever,
            repo_root=repo_root,
            dataset_version=final_settings.dataset_version,
            top_k=final_settings.top_k,
            name=(
                "hybrid-promoted-dense{0}-sparse{1}-candidate{2}-final{3}-dw{4:g}-sw{5:g}-k{6}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    candidate_top_k,
                    final_settings.top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
    if name == "llm_decomposed":
        return LlmDecomposedRetriever(
            final_settings,
            repo_root=repo_root,
            final_top_k=final_settings.top_k,
            subquery_dense_top_k=final_dense_top_k,
            subquery_sparse_top_k=final_sparse_top_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rrf_k=rrf_k,
            name=(
                "llm-decomposed-diverse-dense{0}-sparse{1}-final{2}-dw{3:g}-sw{4:g}-k{5}".format(
                    final_dense_top_k,
                    final_sparse_top_k,
                    final_settings.top_k,
                    dense_weight,
                    sparse_weight,
                    rrf_k,
                )
            ),
        )
    raise ValueError("Unknown retriever: {0}".format(name))
