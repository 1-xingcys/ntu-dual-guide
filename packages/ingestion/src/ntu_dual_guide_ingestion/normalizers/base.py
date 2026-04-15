from __future__ import annotations

import hashlib
from typing import Any


class BaseSilverNormalizer:
    normalizer_name = "base"
    normalizer_version = "v1"

    def build_document(self, bronze_document: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def processing_fingerprint(self, bronze_processing_fingerprint: str) -> str:
        payload = "|".join(
            [
                bronze_processing_fingerprint,
                self.normalizer_name,
                self.normalizer_version,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
