# Evals

Benchmarks and evaluation runners. The benchmark datasets are treated as versioned product-quality assets, not throwaway test data.

The evaluation is split into three layers so that a regression can be traced to the layer that caused it:

| Layer | Evaluates | Dataset | Runner |
|---|---|---|---|
| Retrieval bench | The retriever only | `datasets/retrieval_bench_v1.jsonl` (53 cases) | `retrieval/` |
| Golden bench | End-to-end answers, with deterministic checks | `datasets/golden_bench_v1.jsonl` (63 cases) | `deterministic/` |
| DeepEval | Generation quality, using an LLM as the judge | `datasets/golden_bench_v1.jsonl` | `deepeval/` |

## Retrieval Bench

Scores retrieval without running answer generation. Cases fall into three types: `single-fact`, `multi-fact-compare` and `misleading-single-fact`.

Each case lists `expected_chunk_groups`. Every chunk within a group must be retrieved for the group to count, and retrieving any one group counts as a hit. Reported metrics include Hit@k, Group Recall@k, MRR and Mean Complete RR, overall and per case type.

```bash
# Dense baseline
python3 scripts/eval/eval_retrieval_bench.py --retriever dense

# Hybrid retrieval (current default configuration)
python3 scripts/eval/eval_retrieval_bench.py --retriever hybrid --top-k 10 --dense-top-k 50 --sparse-top-k 50

# Adjust the relative weight of dense and sparse results
python3 scripts/eval/eval_retrieval_bench.py --retriever hybrid --dense-weight 1.0 --sparse-weight 1.5 --rrf-k 60
```

## Golden Bench

Each case contains:

- `case_id`
- `question`
- `expected_answer`
- `expected_status`
- `allow_unknown`
- `expected_answer_contains`
- `expected_source_ids_any`
- `expected_chunk_groups`
- `tags`

The runner applies these checks:

| Check | Description | `rag` mode | `llm_only` mode |
|---|---|:---:|:---:|
| `status_ok` | The answer status matches the expected status | ✓ | ✓ |
| `answer_contains_ok` | The answer contains the required facts | ✓ | ✓ |
| `source_hit_ok` | Retrieval hits an expected source | ✓ | |
| `retrieval_hit_ok` | Retrieval hits an expected chunk group | ✓ | |

`llm_only` mode is a baseline that answers without retrieval, so only the answer checks apply.

```bash
# Full benchmark
python3 scripts/eval/eval_golden_bench.py

# LLM-only baseline
python3 scripts/eval/eval_golden_bench.py --mode llm_only

# Single case
python3 scripts/eval/eval_golden_bench.py --case-id single-fact-001

# Hybrid retriever, with a JSON report
python3 scripts/eval/eval_golden_bench.py --mode rag --retriever hybrid --top-k 10 --dense-top-k 50 --sparse-top-k 50 --min-score 0 --output artifacts/evals/golden_bench_v1.json
```

## DeepEval

DeepEval scores only the generation stage. Retrieval quality is left to the retrieval bench.

| Metric | Applies to | Description |
|---|---|---|
| `GEval` (answer quality) | All modes | Compares the actual answer with the question and the expected answer |
| `FaithfulnessMetric` | `rag` mode with retrieval context | Whether the answer is supported by the retrieved context |
| `HallucinationMetric` | `rag` mode with retrieval context | Lower is better; a score below the threshold passes |

Every case runs the full service, including cases that expect an "unknown" answer. The runner lets generation proceed even when retrieval returns no context, so the judge evaluates the model's actual response rather than a static fallback.

The judge model is `DEEPEVAL_JUDGE_MODEL` if set, otherwise `gpt-4.1-mini`. It is configured separately from `OPENAI_CHAT_MODEL` so the benchmark judge is not tied to the answering model.

```bash
# Full run
.venv/bin/python scripts/eval/eval_deepeval.py --mode rag

# Single case
.venv/bin/python scripts/eval/eval_deepeval.py --case-id single-fact-001

# Hybrid retriever, with a JSON report
.venv/bin/python scripts/eval/eval_deepeval.py --mode rag --retriever hybrid --top-k 10 --dense-top-k 50 --sparse-top-k 50 --min-score 0 --output artifacts/evals/deepeval_hybrid.json
```
