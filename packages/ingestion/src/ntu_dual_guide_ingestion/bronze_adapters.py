from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from ntu_dual_guide_ingestion.bronze_schema import BronzeBlock
from ntu_dual_guide_ingestion.bronze_schema import BronzeContent
from ntu_dual_guide_ingestion.bronze_schema import BronzeDocument
from ntu_dual_guide_ingestion.utils import extract_pdf_text
from ntu_dual_guide_ingestion.utils import extract_title
from ntu_dual_guide_ingestion.utils import normalize_fragment
from ntu_dual_guide_ingestion.utils import normalize_whitespace
from ntu_dual_guide_ingestion.utils import sha256_file


@dataclass
class RawRoute:
    family: str
    category: Optional[str]
    adapter_kind: str
    parser_profile: str


class BaseBronzeAdapter:
    parser_name = "base"
    parser_version = "v1"

    def build_document(
        self,
        raw_path: Path,
        route: RawRoute,
        dataset_version: str,
    ) -> BronzeDocument:
        raise NotImplementedError

    def processing_fingerprint(self, source_hash: str, parser_profile: str) -> str:
        payload = "|".join(
            [source_hash, self.parser_name, self.parser_version, parser_profile]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PdfBronzeAdapter(BaseBronzeAdapter):
    parser_name = "pdftotext"
    parser_version = "v1"

    def __init__(self, layout: bool) -> None:
        self.layout = layout

    def build_document(
        self,
        raw_path: Path,
        route: RawRoute,
        dataset_version: str,
    ) -> BronzeDocument:
        raw_text = extract_pdf_text(raw_path, layout=self.layout)
        source_hash = sha256_file(raw_path)
        blocks = build_pdf_blocks(raw_text, raw_path.stem)

        return BronzeDocument(
            dataset_version=dataset_version,
            raw_path=str(raw_path),
            file_name=raw_path.name,
            file_format="pdf",
            family=route.family,
            category=route.category,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            parser_profile=route.parser_profile,
            source_hash=source_hash,
            processing_fingerprint=self.processing_fingerprint(source_hash, route.parser_profile),
            content=BronzeContent(
                title=blocks[0].text if blocks and blocks[0].block_type == "heading" else raw_path.stem,
                blocks=blocks,
            ),
        )


class HtmlBronzeAdapter(BaseBronzeAdapter):
    parser_name = "html-parser"
    parser_version = "v1"

    def __init__(self, table_aware: bool) -> None:
        self.table_aware = table_aware

    def build_document(
        self,
        raw_path: Path,
        route: RawRoute,
        dataset_version: str,
    ) -> BronzeDocument:
        html_text = raw_path.read_text(encoding="utf-8")
        source_hash = sha256_file(raw_path)
        parser = BronzeHTMLParser(table_aware=self.table_aware)
        parser.feed(html_text)
        blocks = parser.build_blocks()
        title = parser.title or raw_path.stem

        return BronzeDocument(
            dataset_version=dataset_version,
            raw_path=str(raw_path),
            file_name=raw_path.name,
            file_format="html",
            family=route.family,
            category=route.category,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            parser_profile=route.parser_profile,
            source_hash=source_hash,
            processing_fingerprint=self.processing_fingerprint(source_hash, route.parser_profile),
            content=BronzeContent(title=title, blocks=blocks),
        )


def infer_pdf_block_type(text: str, order: int) -> str:
    if order == 0 and len(text) <= 80:
        return "heading"
    if text.startswith(("Q:", "A:", "Q：", "A：")):
        return "qa_marker"
    if text.startswith(("*", "-", "•")):
        return "list_item"
    if text[:2].isdigit() and text[2:3] == ".":
        return "list_item"
    if text.startswith(("1.", "2.", "3.", "4.", "5.")):
        return "list_item"
    if len(text) <= 40 and not text.endswith(("。", "？", "！", ":", "：")):
        return "heading"
    return "paragraph"


def build_pdf_blocks(raw_text: str, fallback_title: str) -> list[BronzeBlock]:
    blocks: list[BronzeBlock] = []
    line_buffer: list[str] = []

    def flush_buffer() -> None:
        if not line_buffer:
            return
        text = normalize_fragment(" ".join(line_buffer))
        line_buffer[:] = []
        if not text:
            return
        block_type = infer_pdf_block_type(text, len(blocks))
        blocks.append(
            BronzeBlock(
                block_id="block-{0:04d}".format(len(blocks) + 1),
                block_type=block_type,
                text=text,
                order=len(blocks) + 1,
            )
        )

    normalized = raw_text.replace("\x0c", "\n")
    for raw_line in normalized.splitlines():
        line = normalize_fragment(raw_line)
        if not line:
            flush_buffer()
            continue
        standalone_type = infer_standalone_pdf_line_type(line, len(blocks))
        if standalone_type:
            flush_buffer()
            blocks.append(
                BronzeBlock(
                    block_id="block-{0:04d}".format(len(blocks) + 1),
                    block_type=standalone_type,
                    text=line,
                    order=len(blocks) + 1,
                )
            )
            continue
        line_buffer.append(line)

    flush_buffer()

    if not blocks:
        blocks.append(
            BronzeBlock(
                block_id="block-0001",
                block_type="paragraph",
                text=fallback_title,
                order=1,
            )
        )
    return blocks


def infer_standalone_pdf_line_type(text: str, order: int) -> Optional[str]:
    block_type = infer_pdf_block_type(text, order)
    if block_type in {"qa_marker", "list_item"}:
        return block_type
    if block_type == "heading" and len(text) <= 80:
        return block_type
    return None


class BronzeHTMLParser(HTMLParser):
    BLOCK_TAGS = {"title", "h1", "h2", "h3", "h4", "h5", "h6", "p", "li"}
    IGNORED_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self, table_aware: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.table_aware = table_aware
        self.ignore_depth = 0
        self.current_tag: Optional[str] = None
        self.current_buffer: list[str] = []
        self.current_row: Optional[list[str]] = None
        self.current_cell: Optional[list[str]] = None
        self.rows: list[list[str]] = []
        self.title: Optional[str] = None
        self.block_specs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.IGNORED_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return
        if self.table_aware and tag == "tr":
            self.current_row = []
            return
        if self.table_aware and tag in {"td", "th"}:
            self.current_cell = []
            return
        if tag in self.BLOCK_TAGS:
            self.current_tag = tag
            self.current_buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORED_TAGS and self.ignore_depth:
            self.ignore_depth -= 1
            return
        if self.ignore_depth:
            return
        if self.table_aware and tag in {"td", "th"} and self.current_cell is not None:
            cell_text = normalize_fragment("".join(self.current_cell))
            if cell_text and self.current_row is not None:
                self.current_row.append(cell_text)
            self.current_cell = None
            return
        if self.table_aware and tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None
            return
        if tag == self.current_tag:
            text = normalize_fragment("".join(self.current_buffer))
            if text:
                block_type = tag if tag != "title" else "heading"
                self.block_specs.append((block_type, text))
                if tag == "title" and not self.title:
                    self.title = text
            self.current_tag = None
            self.current_buffer = []

    def handle_data(self, data: str) -> None:
        if self.ignore_depth:
            return
        if self.current_cell is not None:
            self.current_cell.append(data)
            return
        if self.current_tag is not None:
            self.current_buffer.append(data)

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag == "br":
            if self.current_cell is not None:
                self.current_cell.append("\n")
            elif self.current_buffer is not None:
                self.current_buffer.append("\n")

    def build_blocks(self) -> list[BronzeBlock]:
        blocks: list[BronzeBlock] = []
        for block_type, text in self.block_specs:
            normalized_type = normalize_html_block_type(block_type)
            if normalized_type == "heading" and self.title is None:
                self.title = text
            blocks.append(
                BronzeBlock(
                    block_id="block-{0:04d}".format(len(blocks) + 1),
                    block_type=normalized_type,
                    text=text,
                    order=len(blocks) + 1,
                )
            )
        if self.table_aware:
            for row in self.rows:
                row_text = " | ".join(row)
                blocks.append(
                    BronzeBlock(
                        block_id="block-{0:04d}".format(len(blocks) + 1),
                        block_type="table_row",
                        text=row_text,
                        order=len(blocks) + 1,
                        attributes={"cells": row},
                    )
                )
        return dedupe_blocks(blocks)


def normalize_html_block_type(tag: str) -> str:
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "title"}:
        return "heading"
    if tag == "li":
        return "list_item"
    return "paragraph"


def dedupe_blocks(blocks: list[BronzeBlock]) -> list[BronzeBlock]:
    seen: set[tuple[str, str]] = set()
    deduped: list[BronzeBlock] = []
    for block in blocks:
        key = (block.block_type, block.text)
        if key in seen:
            continue
        seen.add(key)
        block.order = len(deduped) + 1
        block.block_id = "block-{0:04d}".format(block.order)
        deduped.append(block)
    return deduped
