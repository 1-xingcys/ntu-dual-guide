from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import query_vectors_pinecone
from ntu_dual_guide_rag.openai_responses import create_structured_response
from ntu_dual_guide_rag.models import RetrievalChunk
from ntu_dual_guide_rag.retrievers.bm25 import BM25Index
from ntu_dual_guide_rag.retrievers.bm25 import build_bm25_for_dataset
from ntu_dual_guide_rag.retrievers.bm25 import load_records
from ntu_dual_guide_rag.retrievers.bm25 import records_path_for
from ntu_dual_guide_rag.retrievers.protocol import Retriever
from ntu_dual_guide_rag.retrievers.utils import MetadataCatalog
from ntu_dual_guide_rag.retrievers.utils import build_chunk
from ntu_dual_guide_rag.settings import RagSettings


QUERY_PLAN_SCHEMA = {
    "name": "retrieval_query_plan",
    "schema": {
        "type": "object",
        "properties": {
            "subqueries": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A corpus-aligned Traditional Chinese retrieval query asking one factual intent.",
                        },
                        "year_scope": {
                            "type": "string",
                            "description": "Use a concrete year such as 112 when the subquery is year-specific; use all for cross-year/general evidence.",
                        },
                        "department_scope": {
                            "type": "string",
                            "description": "Use a concrete department code such as 3030 or 9020 when department-specific; use all for school-wide/general evidence.",
                        },
                    },
                    "required": ["query", "year_scope", "department_scope"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["subqueries"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass
class PlannedSubquery:
    query: str
    year_scope: str
    department_scope: str
    filters: dict[str, list[str]]


class LlmDecomposedRetriever:
    def __init__(
        self,
        settings: RagSettings,
        *,
        repo_root: Path,
        final_top_k: int,
        subquery_dense_top_k: int,
        subquery_sparse_top_k: int,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
        rrf_k: int = 60,
        name: str = "llm-decomposed-diverse",
        bm25_index: BM25Index | None = None,
    ) -> None:
        self.settings = settings
        self.final_top_k = final_top_k
        self.subquery_dense_top_k = subquery_dense_top_k
        self.subquery_sparse_top_k = subquery_sparse_top_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.rrf_k = rrf_k
        self.name = name
        self.catalog = MetadataCatalog.from_dataset(repo_root, settings.dataset_version)
        self.records_by_id = {
            record["id"]: record
            for record in load_records(records_path_for(repo_root, settings.dataset_version))
        }
        self.bm25 = bm25_index or build_bm25_for_dataset(repo_root, settings.dataset_version)

    def retrieve(self, question: str) -> list[RetrievalChunk]:
        plan = self.plan(question)
        fused_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievalChunk] = {}

        for subquery_index, subquery in enumerate(plan, start=1):
            dense_chunks = self._dense_retrieve(subquery)
            sparse_chunks = self._sparse_retrieve(subquery)
            self._add_ranked_chunks(
                fused_scores,
                chunk_map,
                dense_chunks,
                weight=self.dense_weight,
                subquery_index=subquery_index,
                source="dense",
            )
            self._add_ranked_chunks(
                fused_scores,
                chunk_map,
                sparse_chunks,
                weight=self.sparse_weight,
                subquery_index=subquery_index,
                source="sparse",
            )

        ranked_ids = self._rank_chunk_ids(fused_scores, chunk_map)
        selected_ids = self._select_diverse_chunk_ids(
            ranked_ids,
            chunk_map,
            subquery_count=len(plan),
        )
        chunks: list[RetrievalChunk] = []
        for chunk_id in selected_ids:
            chunk = chunk_map[chunk_id]
            metadata = dict(chunk.metadata)
            metadata["llm_decomposed_score"] = fused_scores[chunk_id]
            chunks.append(
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
        return chunks

    def plan(self, question: str) -> list[PlannedSubquery]:
        plan = create_structured_response(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            instructions=build_planner_instructions(self.catalog.describe_for_prompt()),
            user_input="User query:\n{0}".format(question),
            schema_name=QUERY_PLAN_SCHEMA["name"],
            schema=QUERY_PLAN_SCHEMA["schema"],
            strict=QUERY_PLAN_SCHEMA["strict"],
        )
        subqueries: list[PlannedSubquery] = []
        for item in plan.get("subqueries", []):
            query = str(item.get("query") or "").strip()
            year_scope = str(item.get("year_scope") or "all").strip() or "all"
            department_scope = str(item.get("department_scope") or "all").strip() or "all"
            filters = self.catalog.scope_filters(
                year_scope=year_scope,
                department_scope=department_scope,
            )
            if query:
                subqueries.append(
                    PlannedSubquery(
                        query=query,
                        year_scope=year_scope,
                        department_scope=department_scope,
                        filters=filters,
                    )
                )
        if not subqueries:
            subqueries.append(
                PlannedSubquery(
                    query=question,
                    year_scope="all",
                    department_scope="all",
                    filters={},
                )
            )
        return subqueries

    def _dense_retrieve(self, subquery: PlannedSubquery) -> list[RetrievalChunk]:
        query_vector = embed_texts_openai(
            [subquery.query],
            model=self.settings.openai_embedding_model,
            api_key=self.settings.openai_api_key,
        )[0]
        response = query_vectors_pinecone(
            query_vector,
            namespace=self.settings.namespace,
            index_host=self.settings.pinecone_index_host,
            api_key=self.settings.pinecone_api_key,
            top_k=self.subquery_dense_top_k,
            api_version=self.settings.pinecone_api_version,
            filter=self.catalog.pinecone_filter(subquery.filters),
        )
        chunks: list[RetrievalChunk] = []
        for item in response.get("matches", []):
            metadata = item.get("metadata") or {}
            score = float(item.get("score", 0.0))
            if score < self.settings.min_score:
                continue
            chunks.append(build_chunk(item.get("id", ""), score, metadata))
        return chunks

    def _sparse_retrieve(self, subquery: PlannedSubquery) -> list[RetrievalChunk]:
        pool_size = self.subquery_sparse_top_k if not subquery.filters else self.subquery_sparse_top_k * 5
        hits = self.bm25.search(subquery.query, top_k=pool_size)
        chunks: list[RetrievalChunk] = []
        for chunk_id, score, metadata in hits:
            if subquery.filters and not self.catalog.metadata_matches(metadata, subquery.filters):
                continue
            chunks.append(build_chunk(chunk_id, score, metadata))
            if len(chunks) >= self.subquery_sparse_top_k:
                break
        return chunks

    def _add_ranked_chunks(
        self,
        fused_scores: dict[str, float],
        chunk_map: dict[str, RetrievalChunk],
        chunks: list[RetrievalChunk],
        *,
        weight: float,
        subquery_index: int,
        source: str,
    ) -> None:
        for rank, chunk in enumerate(chunks, start=1):
            contribution = weight / (self.rrf_k + rank)
            fused_scores[chunk.chunk_id] = (
                fused_scores.get(chunk.chunk_id, 0.0) + contribution
            )
            existing = chunk_map.get(chunk.chunk_id)
            if existing is not None:
                existing.metadata.setdefault("retrieval_sources", []).append(
                    {
                        "source": source,
                        "subquery_index": subquery_index,
                        "rank": rank,
                        "rrf_contribution": contribution,
                    }
                )
                continue
            metadata = dict(chunk.metadata)
            metadata["retrieval_sources"] = [
                {
                    "source": source,
                    "subquery_index": subquery_index,
                    "rank": rank,
                    "rrf_contribution": contribution,
                }
            ]
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

    def _rank_chunk_ids(
        self,
        fused_scores: dict[str, float],
        chunk_map: dict[str, RetrievalChunk],
    ) -> list[str]:
        return sorted(
            fused_scores,
            key=lambda chunk_id: (fused_scores[chunk_id], chunk_map[chunk_id].score),
            reverse=True,
        )

    def _select_diverse_chunk_ids(
        self,
        ranked_ids: list[str],
        chunk_map: dict[str, RetrievalChunk],
        *,
        subquery_count: int,
    ) -> list[str]:
        if subquery_count <= 1:
            return ranked_ids[: self.final_top_k]

        ids_by_subquery = self._rank_ids_by_subquery(ranked_ids, chunk_map, subquery_count)
        selected: list[str] = []
        selected_set: set[str] = set()

        for _ in range(self._coverage_quota(subquery_count)):
            for subquery_index in range(1, subquery_count + 1):
                for chunk_id in ids_by_subquery.get(subquery_index, []):
                    if chunk_id in selected_set:
                        continue
                    selected.append(chunk_id)
                    selected_set.add(chunk_id)
                    break
                if len(selected) >= self.final_top_k:
                    return selected

        for chunk_id in ranked_ids:
            if chunk_id in selected_set:
                continue
            selected.append(chunk_id)
            selected_set.add(chunk_id)
            if len(selected) >= self.final_top_k:
                break

        return selected

    def _rank_ids_by_subquery(
        self,
        ranked_ids: list[str],
        chunk_map: dict[str, RetrievalChunk],
        subquery_count: int,
    ) -> dict[int, list[str]]:
        ranked_position = {chunk_id: index for index, chunk_id in enumerate(ranked_ids)}
        ids_by_subquery: dict[int, list[str]] = {}
        for chunk_id in ranked_ids:
            sources = chunk_map[chunk_id].metadata.get("retrieval_sources") or []
            for subquery_index in self._source_subquery_indices(sources, subquery_count):
                ids_by_subquery.setdefault(subquery_index, []).append(chunk_id)

        for subquery_index, chunk_ids in ids_by_subquery.items():
            chunk_ids.sort(
                key=lambda chunk_id: (
                    self._subquery_score(chunk_map[chunk_id], subquery_index),
                    -ranked_position[chunk_id],
                ),
                reverse=True,
            )
        return ids_by_subquery

    def _source_subquery_indices(
        self,
        sources: list[dict],
        subquery_count: int,
    ) -> set[int]:
        indices: set[int] = set()
        for source in sources:
            value = source.get("subquery_index")
            if isinstance(value, int) and 1 <= value <= subquery_count:
                indices.add(value)
        return indices

    def _subquery_score(self, chunk: RetrievalChunk, subquery_index: int) -> float:
        score = 0.0
        for source in chunk.metadata.get("retrieval_sources") or []:
            if source.get("subquery_index") != subquery_index:
                continue
            contribution = source.get("rrf_contribution")
            if isinstance(contribution, (int, float)):
                score += float(contribution)
                continue
            rank = source.get("rank")
            if isinstance(rank, int):
                score += 1.0 / (self.rrf_k + rank)
        return score

    def _coverage_quota(self, subquery_count: int) -> int:
        if subquery_count <= 1:
            return 0
        return max(1, min(2, self.final_top_k // max(1, subquery_count * 2)))


def build_planner_instructions(metadata_catalog: str) -> str:
    return """你是台大雙主修 RAG 系統的「查詢規劃器」。

你的任務是把使用者問題改寫成一個或多個 retrieval subquery。每個 subquery 只查一個事實，並盡量使用語料中會出現的正式用詞。你只能輸出 schema 要求的 JSON。

重要原則：
- 每個 subquery 只能輸出兩個 scope：year_scope 與 department_scope。
- scope 只能使用下方 catalog 列出的值。
- 如果 subquery 查的是跨年度或一般規定，year_scope 使用 all。
- 如果 subquery 查的是校級、跨系所或一般規定，department_scope 使用 all。
- 如果 subquery 明確查某一年度，year_scope 使用該年度，例如 112。
- 如果 subquery 明確查某一系所，department_scope 使用該系所代碼，例如 3030 或 9020。
- 比較題要拆成多個 subquery；每個比較對象各自查詢。

可以使用 year_scope 的情況：
1. 查詢「學系畢業應修學分統計表」中的年度化規定
   - 適用於畢業學分、系選修/院內選修、外文領域、通識、超修課程是否計入選修、畢業應修學分統計表中的規定。
2. 查詢「經濟學系雙主修相關規定（申請規定）」中的年度化規定
   - 適用於申請資格、錄取方式、占分比例、名額、經濟系雙主修申請年度規定。
3. 查詢「系所某年級必修課程」
   - 適用於某學年度、某系、某年級的系訂必修、必修課程清單、個別必修課號/學分。

可以使用 department_scope 的情況：
- subquery 明確查經濟學系、經濟系、ECON、3030 時，使用 3030。
- subquery 明確查資訊工程學系、資工系、CSIE、9020 時，使用 9020。
- subquery 查校級規定、跨系所規定、一般 FAQ 或沒有明確系所時，使用 all。

語料用詞建議：
- 必修課程：系訂必修、必修課程清單、必修科目及學分表。
- 畢業學分規定：畢業應修學分統計表、規定說明、系選修、院內選修、外文領域、通識、計入選修學分。
- 經濟系雙主修申請規定：雙主修相關規定、申請資格、錄取方式及占分比例。
- FAQ/一般規定：雙主修、輔系、學分兼充、外系同名課、統計學課程替代、畢業審查。

{0}

只輸出符合 schema 的 JSON。""".format(metadata_catalog)
