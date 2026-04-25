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
- `src/ntu_dual_guide_evals/deepeval_runner.py`
- `scripts/eval/eval_golden_bench.py`
- `scripts/eval/eval_deepeval.py`

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
- `retrieval_hit_ok`: retrieval 是否命中預期 chunk group

`rag` mode 會完整檢查上述四項。  
`llm_only` mode 只檢查：

- `status_ok`
- `answer_contains_ok`

因為純 LLM baseline 沒有 retrieval。

`expected_chunk_groups` 使用 retrieval bench 相同語意：同一個 group 內的 chunk 必須全部命中；多個 group 之間則命中任一組即可。

### Usage

跑完整 benchmark：

```bash
python3 scripts/eval/eval_golden_bench.py
```

跑純 LLM baseline：

```bash
python3 scripts/eval/eval_golden_bench.py --mode llm_only
```

只跑單題：

```bash
python3 scripts/eval/eval_golden_bench.py --case-id curriculum-csie-111-double-major-001
```

輸出 JSON report：

```bash
python3 scripts/eval/eval_golden_bench.py --output artifacts/evals/golden_bench_v1.json
```

跑 hybrid retriever 的 golden bench：

```bash
python3 scripts/eval/eval_golden_bench.py --mode rag --retriever hybrid --top-k 10 --dense-top-k 50 --sparse-top-k 50 --min-score 0
```

## Why this before DeepEval

這層是 benchmark contract：

- 題目是什麼
- 哪些事實一定要提到
- 哪些 source / chunk 才算 hit

之後接 DeepEval，應該把它放在這層之上，作為 answer quality / faithfulness 的補充，而不是取代這份 benchmark。

## DeepEval Layer

目前先接第一版 DeepEval runner：

- `GEval(answer_quality)`：用 LLM-as-a-judge 比對 question、actual answer、expected answer
- `FaithfulnessMetric`（僅 `rag` mode 且有 retrieval context 時）
- `HallucinationMetric`（僅 `rag` mode 且有 retrieval context 時；分數越低越好，低於 threshold 算成功）

設計原則：

- retrieval hit / source hit 留給 retrieval bench，不在 DeepEval runner 重複判斷
- 每個 case 都照樣呼叫 service 檢索並生成答案，包含預期為 `unknown` 的 nonexistent-fact 題
- DeepEval runner 會讓空 retrieval context 也進入生成，避免用 service 的靜態 fallback 取代生成評估
- DeepEval 只評生成階段：答案是否符合題目與 expected answer、是否避免編造、RAG 答案是否忠於提供 context

執行方式：

```bash
python3 scripts/eval/eval_deepeval.py --mode rag
```

judge model 預設為：

- `DEEPEVAL_JUDGE_MODEL`，若有設定
- 否則 `gpt-4.1-mini`

這和 backend 回答模型分開，避免 benchmark judge 直接綁定 `OPENAI_CHAT_MODEL`。

只跑單題：

```bash
python3 scripts/eval/eval_deepeval.py --case-id comparison-dual-major-vs-minor-001
```

輸出 report：

```bash
python3 scripts/eval/eval_deepeval.py --output artifacts/evals/deepeval_rag.json
```

跑 hybrid retriever 的 DeepEval golden bench：

```bash
python3 scripts/eval/eval_deepeval.py --mode rag --retriever hybrid --top-k 10 --dense-top-k 50 --sparse-top-k 50 --min-score 0 --output artifacts/evals/deepeval_hybrid.json
```

## Retrieval Bench

retrieval bench 用來只看 retriever，不混進 answer generation。

目前可跑：

- `dense`: OpenAI embedding + Pinecone dense retrieval
- `hybrid`: Pinecone dense retrieval + 本機 BM25（用同一份 `records.jsonl`）再做 weighted RRF fusion

執行 dense baseline：

```bash
python3 scripts/eval/eval_retrieval_bench.py --retriever dense
```

執行 application-layer hybrid：

```bash
python3 scripts/eval/eval_retrieval_bench.py --retriever hybrid --top-k 10 --dense-top-k 20 --sparse-top-k 20
```

如果要調整 dense / sparse 相對權重：

```bash
python3 scripts/eval/eval_retrieval_bench.py --retriever hybrid --dense-weight 1.0 --sparse-weight 1.5 --rrf-k 60
```
