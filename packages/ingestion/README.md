# Ingestion

Data engineering for the corpus: parsing, normalization, chunking and indexing. The goal is a pipeline where every index can be rebuilt and every chunk traced back to its source document, not just a one-off load into a vector database.

## Pipeline

| Stage | Entry point | Implementation |
|---|---|---|
| `raw → bronze` | `scripts/etl/raw_to_bronze.py` | `bronze_router.py`, `bronze_adapters.py` |
| `bronze → silver` | `scripts/etl/bronze_to_silver.py` | `silver_router.py`, `normalizers/` |
| `silver → gold` | `scripts/etl/silver_to_gold.py` | `gold_router.py`, `chunkers/` |
| `gold → index records` | `scripts/index/gold_to_index_records.py` | `index_records.py` |
| `index records → Pinecone` | `scripts/index/upsert_pinecone.py` | `vector_clients.py` |

### Layer responsibilities

- **raw**: original PDF and HTML files, organized by source category
- **bronze**: generic parser output, without domain-specific schema
- **silver**: canonical schema for each document class, produced by its normalizer
- **gold**: retrieval-optimized chunks with enrichment metadata such as `year_scope` and `department_scope`

### Parser routing

The `raw → bronze` stage picks a parser profile from the document's folder:

| Raw path | Parser profile |
|---|---|
| `template-family/dpt-double-major-policy/` | `pdf_layout` |
| `template-family/dpt-credit-required/` | `html_table_aware` |
| `template-family/dpt-required-courses/` | `html_table_aware` |
| `source-specific/*.pdf` | `pdf_plain` |
| `source-specific/*.html` | `html_pruned` |

Silver documents are always produced from bronze by a document-class normalizer, never directly from raw files.

## Dataset Snapshots

Every stage requires an explicit `--dataset-version` and writes to a versioned directory:

- `data/bronze/<dataset_version>/`
- `data/silver/<dataset_version>/`
- `data/gold/<dataset_version>/`

Each stage also writes a manifest to `data/manifests/<dataset_version>/<stage>.json`, recording a `source_hash` and processing fingerprint for each document.

```bash
python3 scripts/etl/raw_to_bronze.py    --dataset-version 2026-04-25.001
python3 scripts/etl/bronze_to_silver.py --dataset-version 2026-04-25.001
python3 scripts/etl/silver_to_gold.py   --dataset-version 2026-04-25.001
```

## Indexing

```bash
python3 scripts/index/gold_to_index_records.py --dataset-version 2026-04-25.001
python3 scripts/index/upsert_pinecone.py --dataset-version 2026-04-25.001 --dry-run
python3 scripts/index/upsert_pinecone.py --dataset-version 2026-04-25.001
```

The Pinecone namespace defaults to the dataset version. Upserting requires these environment variables:

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_HOST`

`scripts/index/upsert_pinecone.py` loads `.env` from the repo root. Variables already set in the shell take precedence.
