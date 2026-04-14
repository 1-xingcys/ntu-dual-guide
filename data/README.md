# Data Layout

這個目錄只保留本機開發用結構，不建議把大型 PDF、markdown artifacts 或 embeddings 直接提交到 git。

建議層次：

- `raw/`
- `bronze/`
- `silver/`
- `gold/`

正式環境可把相同結構搬到 object storage。
