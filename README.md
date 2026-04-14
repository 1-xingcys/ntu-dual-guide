# NTU Dual Guide

這個 repo 是一個以台大資工雙主修經濟系為主題的 RAG/LLMOps 專案骨架。目標是把資料工程、檢索問答、評測、前後端與部署拆成清楚的模組，讓系統可以先快速起步，再平滑擴充。

## 設計原則

- `VectorDB` 不是 source of truth；真正的資料真相來自版本化的文件與 manifest。
- `LlamaIndex` 作為 orchestration layer，但核心資料模型與 metadata 規格自行定義，避免被框架綁死。
- ETL、RAG、評測、API、前端、infra 分層，彼此透過明確契約互動。
- 先支援單一學校領域與單一租戶，架構上保留多資料集、多環境與重建 index 的能力。

## 建議 repo 結構

```text
.
├── apps/
│   ├── api/                 # FastAPI / webhook / admin endpoints
│   └── web/                 # 簡單聊天前端
├── configs/
│   ├── pipeline.example.yaml
│   └── sources/
│       └── ntu_csie_econ.example.yaml
├── data/                    # 僅保留本機開發用結構與說明，不把大檔進 git
├── docs/
│   └── architecture.md
├── infra/                   # Docker / deployment / IaC placeholder
├── packages/
│   ├── evals/               # Golden set / DeepEval / benchmark runner
│   ├── ingestion/           # pdf->md->chunk->embed->upsert
│   └── rag/                 # retriever / reranker / prompt / answer service
└── scripts/                 # 開發與操作腳本
```

## 建議技術選型

- ETL / Backend: Python 3.11+, `LlamaIndex`, `FastAPI`
- Vector DB: `Pinecone`
- Frontend: `Next.js` 或任一輕量 chat UI
- CI/CD: `GitHub Actions`
- Evaluation: `DeepEval`
- 儲存策略: local dev 用檔案系統，正式環境用 object storage + manifest snapshot

## 先做的 4 個里程碑

1. 定義文件 metadata schema、dataset snapshot schema、chunking/embedding config。
2. 完成單一來源 ETL pipeline，能從 PDF 進到 Pinecone。
3. 完成最小可用 API 與 chat UI。
4. 建立 Golden Bench 與 CI smoke eval，讓每次改 prompt / retrieval 都可回歸驗證。

詳細規劃看 [docs/architecture.md](/Users/1-xing/Documents/ntu-dual-guide/docs/architecture.md)。
