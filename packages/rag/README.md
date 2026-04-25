# RAG Package

這裡放 runtime 問答邏輯。

建議包含：

- retriever abstraction
- citation builder
- prompt templates
- answer service
- domain schema

這層應與 Web/API transport 分離，方便未來切換為 CLI、batch eval 或其他介面。

## Backend MVP

目前第一版 backend MVP 已包含：

- `PineconeRetriever`: 用 query embedding + Pinecone dense retrieval 取回 context
- `HybridRetriever`: 用 Pinecone dense + 本機 BM25 對 `records.jsonl` 做 application-layer fusion
- `RagService`: 組 prompt，呼叫 OpenAI Responses API，並在無足夠真相時回 `不知道`
- `SYSTEM_PROMPT`: 明確限定模型是「台大資工雙主修經濟系助手」，只能根據學校規定回答
- citation 回傳：先回傳 top retrieved chunks 作為 citation 候選

主要檔案：

- `src/ntu_dual_guide_rag/settings.py`
- `src/ntu_dual_guide_rag/prompts.py`
- `src/ntu_dual_guide_rag/retriever.py`
- `src/ntu_dual_guide_rag/bm25.py`
- `src/ntu_dual_guide_rag/openai_responses.py`
- `src/ntu_dual_guide_rag/service.py`

## Environment

backend MVP 需要這些 `.env` 變數：

```bash
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
PINECONE_API_KEY=...
PINECONE_INDEX_HOST=...
PINECONE_API_VERSION=2026-04
RAG_DATASET_VERSION=2026-04-15.004
RAG_NAMESPACE=2026-04-15.004
RAG_RETRIEVER=hybrid
RAG_TOP_K=10
RAG_DENSE_TOP_K=50
RAG_SPARSE_TOP_K=50
RAG_DENSE_WEIGHT=1.0
RAG_SPARSE_WEIGHT=1.0
RAG_RRF_K=60
RAG_MIN_SCORE=0.55
```

`OPENAI_CHAT_MODEL` 預設是 `gpt-5-mini`。這是因為 OpenAI 官方文件目前把它定位成 cost-optimized reasoning and chat；若之後要更強推理，可以升級到 `gpt-5.2`。

`RagService.from_repo_root()` 預設使用 `hybrid` retriever：Pinecone dense pool 50 + BM25 sparse pool 50，RRF fusion 後回傳 final 10 個 chunks。若要切回 dense，可設定 `RAG_RETRIEVER=dense`。

`HybridRetriever` 另外會讀取：

- `artifacts/index-records/<RAG_DATASET_VERSION>/records.jsonl`

因此 eval 或本機 hybrid 測試時，要確保這份 index records 和 Pinecone namespace 對應的是同一個 dataset snapshot。
