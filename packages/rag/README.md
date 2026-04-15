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
- `RagService`: 組 prompt，呼叫 OpenAI Responses API，並在無足夠真相時回 `不知道`
- `SYSTEM_PROMPT`: 明確限定模型是「台大資工雙主修經濟系助手」，只能根據學校規定回答
- citation 回傳：先回傳 top retrieved chunks 作為 citation 候選

主要檔案：

- `src/ntu_dual_guide_rag/settings.py`
- `src/ntu_dual_guide_rag/prompts.py`
- `src/ntu_dual_guide_rag/retriever.py`
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
RAG_TOP_K=6
RAG_MIN_SCORE=0.55
```

`OPENAI_CHAT_MODEL` 預設是 `gpt-5-mini`。這是因為 OpenAI 官方文件目前把它定位成 cost-optimized reasoning and chat；若之後要更強推理，可以升級到 `gpt-5.2`。
