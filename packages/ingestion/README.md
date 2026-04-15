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

- `scripts/raw_to_bronze.py`
- `ntu_dual_guide_ingestion/bronze_router.py`
- `ntu_dual_guide_ingestion/bronze_adapters.py`

### Layer responsibilities

- `raw`: 原始 PDF / HTML 檔案與來源分類
- `bronze`: 通用 parser 輸出，不含 domain-specific schema
- `silver`: 依 document class 正規化後的 canonical schema
- `gold`: 檢索優化後的 chunks 與 enrichment metadata

### Routing model

`raw` 目前依資料夾分類決定 parser profile：

- `template-family/dpt-double-major-policy` -> `pdf_layout`
- `template-family/dpt-credit-required` -> `html_table_aware`
- `source-specific/*.pdf` -> `pdf_plain`
- `source-specific/*.html` -> `html_pruned`

現有的 `faq_extractor.py` 與 `dual_major_policy_extractor.py` 仍保留為 legacy `raw -> silver` 路徑；之後應逐步改成讀取 `bronze` 再轉 `silver`。
