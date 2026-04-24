"""In-memory BM25 sparse retriever for application-layer hybrid retrieval.

Design notes:
- Tokenizer: ASCII alnum runs (lower-cased) + per-CJK character unigrams +
  CJK character bigrams. This intentionally has zero non-stdlib dependencies
  and keeps numeric tokens like ``113`` / ``CSIE3005`` intact, which are the
  exact signals dense embeddings under-weight.
- Scoring: Okapi BM25 with k1=1.5, b=0.75 (standard defaults).
- Corpus source: the same ``records.jsonl`` that was upserted to Pinecone, so
  chunk_ids and metadata stay aligned with the dense index.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ALNUM_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize a string into BM25 terms.

    Yields ASCII alnum tokens (lower-cased) plus, for the remaining CJK text,
    both unigrams and bigrams. Whitespace and punctuation are dropped. The
    function returns a list (not a set) so callers can build term frequencies.
    """
    if not text:
        return []
    tokens: list[str] = []
    for match in ALNUM_RE.finditer(text):
        tokens.append(match.group(0).lower())
    cjk_only = ALNUM_RE.sub(" ", text)
    cjk_chars: list[str] = []
    for char in cjk_only:
        if char.isspace():
            continue
        # Drop common Chinese and ASCII punctuation; keep CJK + symbols that
        # convey meaning (e.g. + - . slashes are too noisy at char-level).
        if not char.isalnum() and not _is_cjk(char):
            continue
        cjk_chars.append(char)
    tokens.extend(cjk_chars)
    for i in range(len(cjk_chars) - 1):
        tokens.append(cjk_chars[i] + cjk_chars[i + 1])
    return tokens


def _is_cjk(char: str) -> bool:
    code = ord(char)
    # CJK Unified Ideographs + extension A + compatibility ideographs.
    if 0x4E00 <= code <= 0x9FFF:
        return True
    if 0x3400 <= code <= 0x4DBF:
        return True
    if 0xF900 <= code <= 0xFAFF:
        return True
    return False


@dataclass
class BM25Doc:
    chunk_id: str
    metadata: dict


class BM25Index:
    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: list[BM25Doc] = []
        self.doc_lens: list[int] = []
        self.term_freqs: list[dict[str, int]] = []
        self.doc_freq: dict[str, int] = {}
        self.avg_dl: float = 0.0
        self.n: int = 0
        self._idf_cache: dict[str, float] = {}
        # Inverted index: term -> list of (doc_idx, tf). Built lazily on first
        # search to keep ``fit`` cheap and predictable.
        self._postings: dict[str, list[tuple[int, int]]] | None = None

    def fit(self, records: Iterable[dict]) -> None:
        for record in records:
            text = record.get("text") or ""
            tokens = tokenize(text)
            tf = Counter(tokens)
            self.docs.append(
                BM25Doc(
                    chunk_id=record["id"],
                    metadata=record.get("metadata") or {},
                )
            )
            self.term_freqs.append(dict(tf))
            self.doc_lens.append(len(tokens))
            for term in tf:
                self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.n = len(self.docs)
        self.avg_dl = sum(self.doc_lens) / max(self.n, 1)

    def _build_postings(self) -> dict[str, list[tuple[int, int]]]:
        postings: dict[str, list[tuple[int, int]]] = {}
        for doc_idx, tf in enumerate(self.term_freqs):
            for term, freq in tf.items():
                postings.setdefault(term, []).append((doc_idx, freq))
        return postings

    def _idf(self, term: str) -> float:
        cached = self._idf_cache.get(term)
        if cached is not None:
            return cached
        df = self.doc_freq.get(term, 0)
        # Lucene-style IDF, always non-negative. (df can be 0 for unseen
        # query terms; the +0.5/+0.5 keeps the log defined.)
        idf = math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))
        self._idf_cache[term] = idf
        return idf

    def search(self, query: str, *, top_k: int) -> list[tuple[str, float, dict]]:
        q_tokens = tokenize(query)
        if not q_tokens or self.n == 0:
            return []
        if self._postings is None:
            self._postings = self._build_postings()
        scores: dict[int, float] = {}
        seen_terms: set[str] = set()
        for term in q_tokens:
            if term in seen_terms:
                continue
            seen_terms.add(term)
            idf = self._idf(term)
            if idf <= 0:
                continue
            postings = self._postings.get(term)
            if not postings:
                continue
            for doc_idx, freq in postings:
                dl = self.doc_lens[doc_idx]
                denom = freq + self.k1 * (
                    1.0 - self.b + self.b * dl / max(self.avg_dl, 1.0)
                )
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * (
                    freq * (self.k1 + 1.0)
                ) / denom
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]
        return [
            (self.docs[doc_idx].chunk_id, score, self.docs[doc_idx].metadata)
            for doc_idx, score in ranked
        ]


def load_records(records_path: Path) -> list[dict]:
    records: list[dict] = []
    for raw_line in records_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line:
            records.append(json.loads(line))
    return records


def records_path_for(repo_root: Path, dataset_version: str) -> Path:
    return repo_root / "artifacts" / "index-records" / dataset_version / "records.jsonl"


def build_bm25_for_dataset(repo_root: Path, dataset_version: str) -> BM25Index:
    records = load_records(records_path_for(repo_root, dataset_version))
    bm25 = BM25Index()
    bm25.fit(records)
    return bm25
