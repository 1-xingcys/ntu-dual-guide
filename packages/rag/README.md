# RAG Package

這裡放 runtime 問答邏輯。

建議包含：

- retriever abstraction
- citation builder
- prompt templates
- answer service
- domain schema

這層應與 Web/API transport 分離，方便未來切換為 CLI、batch eval 或其他介面。
