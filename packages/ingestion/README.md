# Ingestion Package

這裡放資料工程相關邏輯。

建議結構：

- `connectors/`
- `parsers/`
- `normalizers/`
- `chunkers/`
- `embedders/`
- `indexers/`
- `schemas/`

重點不是只把文件丟進向量庫，而是保留可重建、可追溯的 pipeline。

## Current Flow

目前 repo 內已經有一條 `raw -> bronze` 的通用入口：

- `scripts/etl/raw_to_bronze.py`
- `ntu_dual_guide_ingestion/bronze_router.py`
- `ntu_dual_guide_ingestion/bronze_adapters.py`

以及第一版 `bronze -> silver` 入口：

- `scripts/etl/bronze_to_silver.py`
- `ntu_dual_guide_ingestion/silver_router.py`
- `ntu_dual_guide_ingestion/normalizers/`

以及第一版 `silver -> gold` 入口：

- `scripts/etl/silver_to_gold.py`
- `ntu_dual_guide_ingestion/gold_router.py`
- `ntu_dual_guide_ingestion/chunkers/`

以及 `gold -> index records -> Pinecone` 入口：

- `scripts/index/gold_to_index_records.py`
- `scripts/index/upsert_pinecone.py`
- `ntu_dual_guide_ingestion/index_records.py`
- `ntu_dual_guide_ingestion/vector_clients.py`

### Layer responsibilities

- `raw`: 原始 PDF / HTML 檔案與來源分類
- `bronze`: 通用 parser 輸出，不含 domain-specific schema
- `silver`: 依 document class 正規化後的 canonical schema
- `gold`: 檢索優化後的 chunks 與 enrichment metadata

### Routing model

`raw` 目前依資料夾分類決定 parser profile：

- `template-family/dpt-double-major-policy` -> `pdf_layout`
- `template-family/dpt-credit-required` -> `html_table_aware`
- `template-family/dpt-required-courses` -> `html_table_aware`
- `source-specific/*.pdf` -> `pdf_plain`
- `source-specific/*.html` -> `html_pruned`

目前應以 `raw -> bronze -> silver` 為主流程；`silver` 由 `document class` normalizer 產生，不再直接由 `raw` 輸出。

### Dataset snapshots

三個 stage script 現在都必須顯式帶 `--dataset-version`，而且會把輸出寫到版本化目錄：

- `data/bronze/<dataset_version>/...`
- `data/silver/<dataset_version>/...`
- `data/gold/<dataset_version>/...`

同時每個 stage 會寫 manifest 到：

- `data/manifests/<dataset_version>/raw_to_bronze.json`
- `data/manifests/<dataset_version>/bronze_to_silver.json`
- `data/manifests/<dataset_version>/silver_to_gold.json`

範例：

```bash
python3 scripts/etl/raw_to_bronze.py --dataset-version 2026-04-15.001
python3 scripts/etl/bronze_to_silver.py --dataset-version 2026-04-15.001
python3 scripts/etl/silver_to_gold.py --dataset-version 2026-04-15.001
```

索引階段範例：

```bash
python3 scripts/index/gold_to_index_records.py --dataset-version 2026-04-15.003
python3 scripts/index/upsert_pinecone.py --dataset-version 2026-04-15.003 --dry-run
python3 scripts/index/upsert_pinecone.py --dataset-version 2026-04-15.003
```

實際 upsert 需要這些環境變數：

- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_HOST`

`scripts/index/upsert_pinecone.py` 會自動讀 repo root 的 `.env`，且已存在的 shell 環境變數優先。
