from __future__ import annotations

import hashlib
from typing import Any


class BaseGoldChunker:
    chunker_name = "base_chunker"
    chunker_version = "v1"

    def build_document(self, silver_document: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def processing_fingerprint(self, silver_processing_fingerprint: str) -> str:
        payload = "|".join(
            [
                silver_processing_fingerprint,
                self.chunker_name,
                self.chunker_version,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
