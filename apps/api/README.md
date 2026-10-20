# API

The transport layer, built with FastAPI. It validates requests, calls the service layer in `packages/rag` and streams results to clients. Retrieval and prompt logic stay in `packages/rag`, and ETL and index management stay in `packages/ingestion`.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Health check |
| `POST` | `/v1/chat` | Returns the full answer with citations |
| `POST` | `/v1/chat/stream` | Streams the answer as Server-Sent Events |

`/v1/chat/stream` emits these events in order:

| Event | Payload |
|---|---|
| `stage` | Current pipeline stage |
| `retrieved` | Retrieved chunk IDs, scores, titles and source IDs |
| `reasoning` / `token` | Incremental reasoning summary and answer text |
| `final` | The complete answer with citations |
| `error` | Error message, if the request fails |
| `done` | End of stream |

## Running Locally

```bash
.venv/bin/uvicorn apps.api.main:app --reload
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"資工系學生修讀他系之雙主修必修科目及指定選修學分會怎麼計算？"}'
```

The request body has a single `message` field.
