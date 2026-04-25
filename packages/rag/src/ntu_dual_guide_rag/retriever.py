from __future__ import annotations

from pathlib import Path
import re
from typing import Protocol, runtime_checkable

from ntu_dual_guide_ingestion.vector_clients import embed_texts_openai
from ntu_dual_guide_ingestion.vector_clients import query_vectors_pinecone
from ntu_dual_guide_rag.bm25 import BM25Index
from ntu_dual_guide_rag.bm25 import build_bm25_for_dataset
from ntu_dual_guide_rag.bm25 import load_records
from ntu_dual_guide_rag.bm25 import records_path_for
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
            chunks.append(build_chunk(item.get("id", ""), score, metadata))
        return chunks


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


class RelatedChunkIndex:
    def __init__(self, records: list[dict]) -> None:
        self.records_by_id = {record["id"]: record for record in records}
        self.ids_by_required_list_key: dict[tuple[str, str, str], str] = {}
        self.ids_by_course_key: dict[tuple[str, str, str, str], str] = {}
        self.curriculum_notes: list[dict] = []
        self.policy_sections: list[dict] = []
        for record in records:
            metadata = record.get("metadata") or {}
            chunk_type = metadata.get("chunk_type")
            department_code = str(metadata.get("department_code") or "")
            admission_year = str(metadata.get("admission_year") or "")
            grade = str(metadata.get("grade") or "")
            if chunk_type == "required_courses_list" and department_code and admission_year and grade:
                self.ids_by_required_list_key[
                    (department_code, admission_year, grade)
                ] = record["id"]
            if chunk_type == "required_course" and department_code and admission_year and grade:
                chinese_name = str(metadata.get("chinese_name") or "")
                if chinese_name:
                    self.ids_by_course_key[
                        (department_code, admission_year, grade, chinese_name)
                    ] = record["id"]
            if chunk_type in {"curriculum_note", "curriculum_note_item"}:
                self.curriculum_notes.append(record)
            if chunk_type == "policy_section":
                self.policy_sections.append(record)

    @classmethod
    def from_dataset(cls, repo_root: Path, dataset_version: str) -> "RelatedChunkIndex":
        return cls(load_records(records_path_for(repo_root, dataset_version)))

    def build_chunk(self, chunk_id: str, score: float) -> RetrievalChunk | None:
        record = self.records_by_id.get(chunk_id)
        if record is None:
            return None
        return build_chunk(chunk_id, score, record.get("metadata") or {})

    def related_ids_for(self, chunk: RetrievalChunk) -> list[str]:
        metadata = chunk.metadata
        chunk_type = metadata.get("chunk_type")
        source_id = str(metadata.get("source_id") or "")
        related: list[str] = []
        if chunk_type == "required_course" and source_id:
            related.append("{0}-list".format(source_id))
        if chunk_type == "curriculum_note_item" and source_id and metadata.get("note_index"):
            related.append(
                "{0}-note-{1:03d}".format(source_id, int(metadata["note_index"]))
            )
        return [chunk_id for chunk_id in related if chunk_id in self.records_by_id]

    def query_related_ids(self, question: str) -> list[str]:
        ids: list[str] = []
        ids.extend(self._required_course_query_ids(question))
        ids.extend(self._curriculum_note_query_ids(question))
        ids.extend(self._policy_query_ids(question))
        deduped: list[str] = []
        seen: set[str] = set()
        for chunk_id in ids:
            if chunk_id in seen or chunk_id not in self.records_by_id:
                continue
            seen.add(chunk_id)
            deduped.append(chunk_id)
        return deduped

    def _required_course_query_ids(self, question: str) -> list[str]:
        has_required_list_intent = "必修" in question
        departments = infer_departments(question)
        years = infer_years(question)
        department_year_pairs = infer_department_year_pairs(question)
        grades = infer_grades(question)
        if not grades and ("共同必修" in question or "重疊" in question):
            grades = ["1"]
        if not grades and "所有年級" in question:
            grades = ["1", "2", "3", "4"]
        if not department_year_pairs:
            department_year_pairs = [
                (department, year)
                for department in departments
                for year in years
            ]
        ids: list[str] = []
        if has_required_list_intent:
            for department, year in department_year_pairs:
                for grade in grades:
                    list_id = self.ids_by_required_list_key.get((department, year, grade))
                    if list_id:
                        ids.append(list_id)
        for (department, year, grade, course_name), chunk_id in self.ids_by_course_key.items():
            if department_year_pairs and (department, year) not in department_year_pairs:
                continue
            if not department_year_pairs:
                if departments and department not in departments:
                    continue
                if years and year not in years:
                    continue
            if grades and grade not in grades:
                continue
            if course_name and course_name in question:
                ids.append(chunk_id)
        return ids

    def _curriculum_note_query_ids(self, question: str) -> list[str]:
        keyword_groups = curriculum_note_keyword_groups(question)
        if not keyword_groups:
            return []
        departments = set(infer_departments(question))
        years = set(infer_years(question))
        department_year_pairs = set(infer_department_year_pairs(question))
        if not years and not department_year_pairs:
            return []
        has_external_area_keyword = "外文" in question or "通識" in question
        has_elective_keyword = "系選修" in question or "選修" in question
        ids: list[str] = []
        for record in self.curriculum_notes:
            metadata = record.get("metadata") or {}
            chunk_type = str(metadata.get("chunk_type") or "")
            if has_external_area_keyword and chunk_type != "curriculum_note_item":
                continue
            if has_elective_keyword and not has_external_area_keyword and chunk_type != "curriculum_note":
                continue
            department = str(metadata.get("department_code") or "")
            year = str(metadata.get("admission_year") or "")
            if department_year_pairs:
                if (department, year) not in department_year_pairs:
                    continue
            else:
                if departments and department not in departments:
                    continue
                if years and year not in years:
                    continue
            text = str(record.get("text") or "")
            if any(any(keyword in text for keyword in group) for group in keyword_groups):
                ids.append(record["id"])
        return ids

    def _policy_query_ids(self, question: str) -> list[str]:
        section_ids: list[str] = []
        if "申請資格" in question:
            section_ids.append("eligibility")
        if "錄取方式" in question or "占分" in question:
            section_ids.append("selection_method_and_weight")
        if not section_ids:
            return []
        years = set(infer_years(question))
        ids: list[str] = []
        for record in self.policy_sections:
            metadata = record.get("metadata") or {}
            year = str(metadata.get("academic_year") or "")
            section_id = str(metadata.get("section_id") or "")
            if years and year not in years:
                continue
            if section_id in section_ids:
                ids.append(record["id"])
        return ids


def infer_departments(question: str) -> list[str]:
    departments: list[str] = []
    if any(alias in question for alias in ["資工", "資訊工程", "CSIE", "9020"]):
        departments.append("9020")
    if any(alias in question for alias in ["經濟", "ECON", "3030"]):
        departments.append("3030")
    return departments


def infer_department_year_pairs(question: str) -> list[tuple[str, str]]:
    departments = department_mentions(question)
    years = [(match.group(1), match.start(), match.end()) for match in YEAR_RE.finditer(question)]
    if not departments or not years:
        return []
    if len(years) == 1:
        return [(department, years[0][0]) for department, _, _ in departments]

    pairs: list[tuple[str, str]] = []
    for department, start, end in departments:
        before = question[max(0, start - 8) : start]
        after = question[end : end + 8]
        before_years = [match.group(1) for match in YEAR_RE.finditer(before)]
        after_years = [match.group(1) for match in YEAR_RE.finditer(after)]
        if before_years and ("學年度" in before or "學年" in before):
            year = before_years[-1]
        elif after_years:
            year = after_years[0]
        elif before_years:
            year = before_years[-1]
        else:
            center = (start + end) / 2
            year = min(
                years,
                key=lambda item: abs(((item[1] + item[2]) / 2) - center),
            )[0]
        pairs.append((department, year))
    return sorted(set(pairs))


def department_mentions(question: str) -> list[tuple[str, int, int]]:
    mentions: list[tuple[str, int, int]] = []
    for match in DEPARTMENT_RE.finditer(question):
        token = match.group(0)
        department = "9020" if token in {"資工", "資訊工程", "CSIE", "9020"} else "3030"
        mentions.append((department, match.start(), match.end()))
    return mentions


def infer_years(question: str) -> list[str]:
    return sorted(set(match.group(1) for match in YEAR_RE.finditer(question)))


def infer_grades(question: str) -> list[str]:
    grade_patterns = [
        ("1", ("一年級", "大一", "1年級", "一年")),
        ("2", ("二年級", "大二", "2年級", "二年")),
        ("3", ("三年級", "大三", "3年級", "三年")),
        ("4", ("四年級", "大四", "4年級", "四年")),
    ]
    grades = [grade for grade, aliases in grade_patterns if any(alias in question for alias in aliases)]
    return sorted(set(grades))


def curriculum_note_keyword_groups(question: str) -> list[tuple[str, ...]]:
    groups: list[tuple[str, ...]] = []
    if "系選修" in question or "選修" in question:
        groups.append(("系選修", "系訂選修", "院內選修", "選修科目", "本系課程"))
    if "外文" in question:
        groups.append(("外文", "外(英)文"))
    if "通識" in question:
        groups.append(("通識",))
    return groups


YEAR_RE = re.compile(r"(?<!\d)(1[01][0-9]|12[0-9])(?!\d)")
DEPARTMENT_RE = re.compile(r"資工|資訊工程|CSIE|9020|經濟|ECON|3030")


def build_chunk(chunk_id: str, score: float, metadata: dict) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk_id,
        score=score,
        source_id=metadata.get("source_id", ""),
        doc_type=metadata.get("doc_type", ""),
        chunk_type=metadata.get("chunk_type", ""),
        title=metadata.get("chunk_title") or metadata.get("title") or "",
        text=metadata.get("chunk_text", ""),
        metadata=metadata,
    )


def replace_chunk_score(chunk: RetrievalChunk, score: float) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk.chunk_id,
        score=score,
        source_id=chunk.source_id,
        doc_type=chunk.doc_type,
        chunk_type=chunk.chunk_type,
        title=chunk.title,
        text=chunk.text,
        metadata=chunk.metadata,
    )


def replace_chunk_metadata(chunk: RetrievalChunk, metadata: dict) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=chunk.chunk_id,
        score=chunk.score,
        source_id=chunk.source_id,
        doc_type=chunk.doc_type,
        chunk_type=chunk.chunk_type,
        title=chunk.title,
        text=chunk.text,
        metadata=metadata,
    )
