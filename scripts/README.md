# Scripts

Scripts are grouped by purpose:

| Directory | Purpose |
|---|---|
| `scripts/fetch/` | Download source documents into `data/raw/` |
| `scripts/etl/` | Run the `raw → bronze → silver → gold` stages |
| `scripts/index/` | Build index records from gold chunks and upsert them to Pinecone |
| `scripts/eval/` | Run the retrieval bench, golden bench and DeepEval |
| `scripts/rag/` | Ask questions and inspect retrieval from the command line |

Scripts that run in CI/CD should stay stateless and idempotent.
