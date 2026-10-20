# Data

This directory holds the local data layers. Source documents, intermediate artifacts and embeddings are not committed to git; run `scripts/fetch/fetch_raw.py` to download the source documents.

| Layer | Contents |
|---|---|
| `raw/` | Original PDF and HTML source documents |
| `bronze/<dataset_version>/` | Generic parser output, without domain-specific schema |
| `silver/<dataset_version>/` | Canonical documents produced by document-class normalizers |
| `gold/<dataset_version>/` | Retrieval-ready chunks with enrichment metadata |
| `manifests/<dataset_version>/` | Stage manifests for each dataset snapshot (tracked in git) |

In a production setup, the same layout can be moved to object storage.
