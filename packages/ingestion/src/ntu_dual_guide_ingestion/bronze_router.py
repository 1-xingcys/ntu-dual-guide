from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ntu_dual_guide_ingestion.bronze_adapters import HtmlBronzeAdapter
from ntu_dual_guide_ingestion.bronze_adapters import PdfBronzeAdapter
from ntu_dual_guide_ingestion.bronze_adapters import RawRoute


KNOWN_FAMILIES = {"template-family", "source-family", "source-specific"}


class RawToBronzeRouter:
    def __init__(self) -> None:
        self.adapters = {
            "pdf_plain": PdfBronzeAdapter(layout=False),
            "pdf_layout": PdfBronzeAdapter(layout=True),
            "html_pruned": HtmlBronzeAdapter(table_aware=False),
            "html_table_aware": HtmlBronzeAdapter(table_aware=True),
        }

    def resolve(self, raw_path: Path, raw_root: Path) -> RawRoute:
        relative_path = raw_path.relative_to(raw_root)
        parts = relative_path.parts
        family = parts[0] if parts and parts[0] in KNOWN_FAMILIES else "unclassified"
        category = parts[1] if family in {"template-family", "source-family"} and len(parts) > 2 else None
        suffix = raw_path.suffix.lower()

        if suffix == ".pdf" and family == "template-family" and category == "dpt-double-major-policy":
            return RawRoute(family=family, category=category, adapter_kind="pdf", parser_profile="pdf_layout")
        if suffix == ".html" and family == "template-family" and category == "dpt-credit-required":
            return RawRoute(
                family=family,
                category=category,
                adapter_kind="html",
                parser_profile="html_table_aware",
            )
        if suffix == ".pdf":
            return RawRoute(family=family, category=category, adapter_kind="pdf", parser_profile="pdf_plain")
        if suffix == ".html":
            return RawRoute(family=family, category=category, adapter_kind="html", parser_profile="html_pruned")
        raise ValueError("Unsupported raw file type: {0}".format(raw_path))

    def build_bronze_document(self, raw_path: Path, raw_root: Path) -> dict:
        route = self.resolve(raw_path, raw_root)
        adapter = self.adapters[route.parser_profile]
        return adapter.build_document(raw_path, route).to_dict()


def iter_raw_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*")):
        if path.is_file() and path.name not in {".DS_Store", ".gitkeep"}:
            yield path


def bronze_output_path(raw_path: Path, raw_root: Path, bronze_root: Path) -> Path:
    relative_path = raw_path.relative_to(raw_root)
    return bronze_root / relative_path.with_suffix(".json")


def write_bronze_document(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
