# Evals Package

這裡放 Golden Bench 與評測程式。

建議分開管理：

- `datasets/`: golden questions / expected facts
- `runners/`: DeepEval 執行器
- `reports/`: benchmark 輸出

Golden Bench 應被視為產品品質資產，而不是臨時測試資料。

## Current Baseline

目前已建立：

- `datasets/golden_bench_v1.jsonl`
- `src/ntu_dual_guide_evals/golden_bench.py`
- `src/ntu_dual_guide_evals/runner.py`
- `scripts/eval_golden_bench.py`

這一版先做 deterministic baseline，不依賴 DeepEval。

### Dataset schema

每一題至少包含：

- `case_id`
- `question`
- `expected_status`
- `allow_unknown`
- `expected_answer_contains`
- `expected_source_ids_any`
- `expected_retrieved_chunk_ids_any`
- `tags`

### Runner checks

目前 runner 會檢查：

- `status_ok`: 回答狀態是否符合預期
- `answer_contains_ok`: 答案是否包含必要關鍵事實
- `source_hit_ok`: retrieval 是否命中預期 source family
- `retrieval_hit_ok`: retrieval 是否命中預期 chunk

`rag` mode 會完整檢查上述四項。  
`llm_only` mode 只檢查：

- `status_ok`
- `answer_contains_ok`

因為純 LLM baseline 沒有 retrieval。

### Usage

跑完整 benchmark：

```bash
python3 scripts/eval_golden_bench.py
```

跑純 LLM baseline：

```bash
python3 scripts/eval_golden_bench.py --mode llm_only
```

只跑單題：

```bash
python3 scripts/eval_golden_bench.py --case-id curriculum-csie-111-double-major-001
```

輸出 JSON report：

```bash
python3 scripts/eval_golden_bench.py --output artifacts/evals/golden_bench_v1.json
```

## Why this before DeepEval

這層是 benchmark contract：

- 題目是什麼
- 哪些事實一定要提到
- 哪些 source / chunk 才算 hit

之後接 DeepEval，應該把它放在這層之上，作為 answer quality / faithfulness 的補充，而不是取代這份 benchmark。
