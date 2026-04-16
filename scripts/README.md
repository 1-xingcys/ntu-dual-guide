# Scripts

腳本依用途分目錄：

- `scripts/fetch/`
  - 抓原始資料到 `data/raw`
- `scripts/etl/`
  - `raw -> bronze -> silver -> gold`
- `scripts/index/`
  - `gold -> index records -> Pinecone`
- `scripts/eval/`
  - benchmark / golden bench
- `scripts/rag/`
  - 本機 CLI 問答與 retrieval 驗證

如果某支腳本會被 CI/CD 使用，優先讓它保持無狀態且可重複執行。
