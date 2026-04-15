# API App

這裡放對外服務層，建議使用 `FastAPI`。

責任：

- 暴露 chat / health / feedback endpoints
- 驗證 request/response schema
- 呼叫 `packages/rag` 的 service layer
- 記錄 trace 與 observability

不建議：

- 在 route handler 內直接寫 retrieval / prompt business logic
- 在這層直接做 ETL 或 index 管理

## Current MVP

目前已提供：

- `GET /healthz`
- `POST /v1/chat`

啟動方式：

```bash
uvicorn apps.api.main:app --reload
```

若使用 `uv` 建好的虛擬環境：

```bash
.venv/bin/uvicorn apps.api.main:app --reload
```

request body：

```json
{
  "message": "資工系學生修讀他系之雙主修必修科目及指定選修學分會怎麼計算？"
}
```

本機測試：

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"資工系學生修讀他系之雙主修必修科目及指定選修學分會怎麼計算？"}'
```
