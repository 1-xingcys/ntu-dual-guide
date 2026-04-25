from __future__ import annotations

from pathlib import Path
import re

from ntu_dual_guide_rag.models import RetrievalChunk
from ntu_dual_guide_rag.retrievers.bm25 import load_records, records_path_for


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
                self.ids_by_required_list_key[(department_code, admission_year, grade)] = record["id"]
            if chunk_type == "required_course" and department_code and admission_year and grade:
                chinese_name = str(metadata.get("chinese_name") or "")
                if chinese_name:
                    self.ids_by_course_key[(department_code, admission_year, grade, chinese_name)] = record[
                        "id"
                    ]
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
            related.append("{0}-note-{1:03d}".format(source_id, int(metadata["note_index"])))
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
            department_year_pairs = [(department, year) for department in departments for year in years]
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

