from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ntu_dual_guide_ingestion.normalizers.curriculum_required import BronzeCurriculumRequiredNormalizer
from ntu_dual_guide_ingestion.normalizers.dual_major_policy import BronzeDualMajorPolicyNormalizer
from ntu_dual_guide_ingestion.normalizers.faq import BronzeFaqNormalizer
from ntu_dual_guide_ingestion.normalizers.sectioned_source import BronzeSectionedSourceNormalizer


class BronzeToSilverRouter:
    def __init__(self) -> None:
        self.faq_normalizer = BronzeFaqNormalizer()
        self.dual_major_policy_normalizer = BronzeDualMajorPolicyNormalizer()
        self.curriculum_required_normalizer = BronzeCurriculumRequiredNormalizer()
        self.econ_portal_normalizer = BronzeSectionedSourceNormalizer(
            doc_type="econ_portal_page",
            source_id="econ-transfer-double-major-portal",
        )
        self.csie_handbook_normalizer = BronzeSectionedSourceNormalizer(
            doc_type="handbook",
            source_id="csie-handbook-112",
            authority_level="primary",
        )
        self.ntu_policy_info_normalizer = BronzeSectionedSourceNormalizer(
            doc_type="ntu_policy_info_page",
            source_id="ntu-transfer-minor-double-major-info",
            authority_level="primary",
        )

    def resolve(self, bronze_document: dict) -> object:
        category = bronze_document.get("category")
        title = bronze_document.get("content", {}).get("title", "")
        file_name = bronze_document.get("file_name", "")

        if category == "dpt-double-major-policy":
            return self.dual_major_policy_normalizer
        if category == "dpt-credit-required":
            return self.curriculum_required_normalizer
        if "常見Q&A" in title or "常見Q_A" in file_name or "雙主修_輔系常見Q_A" in file_name:
            return self.faq_normalizer
        if "轉雙輔招生頁面" in file_name:
            return self.econ_portal_normalizer
        if "新生手冊" in file_name:
            return self.csie_handbook_normalizer
        if "轉系、輔系及雙主修相關規定查詢網頁" in file_name:
            return self.ntu_policy_info_normalizer
        raise ValueError("No silver normalizer configured for bronze document: {0}".format(file_name))

    def build_silver_document(self, bronze_path: Path) -> dict:
        bronze_document = json.loads(bronze_path.read_text(encoding="utf-8"))
        normalizer = self.resolve(bronze_document)
        return normalizer.build_document(bronze_document)


def iter_bronze_files(input_path: Path) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return
    for path in sorted(input_path.rglob("*.json")):
        if path.is_file():
            yield path


def silver_output_path(bronze_path: Path, bronze_root: Path, silver_root: Path) -> Path:
    relative_path = bronze_path.relative_to(bronze_root)
    return silver_root / relative_path


def write_silver_document(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
