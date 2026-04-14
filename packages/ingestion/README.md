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
