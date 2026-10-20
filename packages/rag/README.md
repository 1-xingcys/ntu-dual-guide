# RAG

Runtime question answering: retrieval, prompting and answer generation. This layer is independent of the web and API transport, so the same service runs behind the API, the CLI and batch evaluation.

## Components

| Component | File | Description |
|---|---|---|
| `PineconeRetriever` | `retrievers/pinecone.py` | Dense retrieval with OpenAI embeddings and Pinecone |
| `BM25Index` | `retrievers/bm25.py` | Local sparse retrieval over the dataset's `records.jsonl` |
| `HybridRetriever` | `retrievers/hybrid.py` | Fuses dense and sparse results with weighted Reciprocal Rank Fusion |
| `LlmDecomposedRetriever` | `retrievers/llm_decomposed.py` | Uses an LLM planner to split a question into scoped sub-queries, then fuses their results |
| `PromotedRetriever` | `retrievers/promoted.py` | Post-processes a base retriever by promoting related chunks |
| `RagService` | `service.py` | Builds the prompt, calls the OpenAI Responses API and streams the answer with citations |
| Prompts | `prompts.py` | System prompts that restrict answers to the provided school regulations |
| Settings | `settings.py` | Configuration loaded from environment variables |

`retrievers/factory.py` builds a retriever by name: `dense`, `hybrid`, `hybrid_promoted` or `llm_decomposed`.

When retrieval returns no relevant context, `RagService` answers that it does not know instead of generating an unsupported answer.

## Configuration

`RagService.from_repo_root()` reads these variables from `.env`:

```bash
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
PINECONE_API_KEY=...
PINECONE_INDEX_HOST=...
PINECONE_API_VERSION=2026-04
RAG_DATASET_VERSION=2026-04-25.001
RAG_NAMESPACE=2026-04-25.001
RAG_RETRIEVER=hybrid
RAG_TOP_K=10
RAG_DENSE_TOP_K=50
RAG_SPARSE_TOP_K=50
RAG_DENSE_WEIGHT=1.0
RAG_SPARSE_WEIGHT=1.0
RAG_RRF_K=60
RAG_MIN_SCORE=0.55
```

`RAG_DATASET_VERSION` is required. `RAG_NAMESPACE` defaults to the dataset version.

The default retriever is `hybrid`: a dense pool of 50 and a sparse pool of 50, fused with RRF into a final 10 chunks. Set `RAG_RETRIEVER=dense` to use dense retrieval only.

`HybridRetriever` also reads `artifacts/index-records/<RAG_DATASET_VERSION>/records.jsonl` to build the BM25 index. This file and the Pinecone namespace must come from the same dataset snapshot.
