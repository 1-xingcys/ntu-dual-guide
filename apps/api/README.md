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
