# Retrieval Experiment Summary 2026-04-25

## Setup

- Dataset version: `2026-04-25.001`
- Namespace: `2026-04-25.001`
- Benchmark: `packages/evals/datasets/retrieval_bench_v1.jsonl`
- Total cases: 53
  - `single-fact`: 28
  - `multi-fact-compare`: 15
  - `misleading-single-fact`: 10
- All valid runs below have `error_rate = 0.0`.
- `hybrid_promoted` was intentionally not rerun for this round.

## Overall Results

| Run | Retriever | Top-k behavior | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Hit@50 | Group Recall@10 | Group Recall@50 | MRR | Mean Complete RR |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense@10 | `dense-pinecone-top10` | dense final 10 | 0.377 | 0.434 | 0.509 | 0.585 | - | 0.668 | - | 0.545 | 0.433 |
| Hybrid@10 | `hybrid-rrf-dense10-sparse10` | dense 10 + sparse 10, final 10 | 0.453 | 0.528 | 0.566 | 0.604 | - | 0.714 | - | 0.660 | 0.502 |
| Dense@50 | `dense-pinecone-top50` | dense final 50 | 0.377 | 0.434 | 0.509 | 0.585 | 0.849 | 0.668 | 0.928 | 0.559 | 0.448 |
| Hybrid pool50 final10 | `hybrid-rrf-dense50-sparse50` | dense 50 + sparse 50, final 10 | 0.472 | 0.547 | 0.585 | 0.717 | - | 0.836 | - | 0.722 | 0.533 |
| Hybrid pool50 final50 | `hybrid-rrf-dense50-sparse50` | dense 50 + sparse 50, final 50 | 0.472 | 0.547 | 0.585 | 0.717 | 0.830 | 0.836 | 0.904 | 0.723 | 0.538 |
| LLM decomposed scope | `llm-decomposed-dense10-sparse10` | subquery dense 10 + sparse 10, final 10 | 0.415 | 0.547 | 0.604 | 0.736 | - | 0.791 | - | 0.625 | 0.504 |
| LLM decomposed diverse | `llm-decomposed-diverse-dense10-sparse10` | coverage-aware final 10 | 0.415 | 0.566 | 0.660 | 0.736 | - | 0.805 | - | 0.670 | 0.516 |

## Results By Case Type

### Hit@10

| Run | Single-fact | Multi-fact compare | Misleading single-fact |
|---|---:|---:|---:|
| Dense@10 | 0.821 | 0.200 | 0.500 |
| Hybrid@10 | 0.857 | 0.133 | 0.600 |
| Dense@50 | 0.821 | 0.200 | 0.500 |
| Hybrid pool50 final10 | 0.929 | 0.400 | 0.600 |
| Hybrid pool50 final50 | 0.929 | 0.400 | 0.600 |
| LLM decomposed scope | 0.857 | 0.533 | 0.700 |
| LLM decomposed diverse | 0.893 | 0.467 | 0.700 |

### Group Recall@10

| Run | Single-fact | Multi-fact compare | Misleading single-fact |
|---|---:|---:|---:|
| Dense@10 | 0.821 | 0.439 | 0.583 |
| Hybrid@10 | 0.857 | 0.378 | 0.817 |
| Dense@50 | 0.821 | 0.439 | 0.583 |
| Hybrid pool50 final10 | 0.929 | 0.678 | 0.817 |
| Hybrid pool50 final50 | 0.929 | 0.678 | 0.817 |
| LLM decomposed scope | 0.857 | 0.650 | 0.817 |
| LLM decomposed diverse | 0.893 | 0.633 | 0.817 |

### MRR

| Run | Single-fact | Multi-fact compare | Misleading single-fact |
|---|---:|---:|---:|
| Dense@10 | 0.653 | 0.290 | 0.625 |
| Hybrid@10 | 0.733 | 0.476 | 0.733 |
| Dense@50 | 0.663 | 0.310 | 0.639 |
| Hybrid pool50 final10 | 0.774 | 0.576 | 0.795 |
| Hybrid pool50 final50 | 0.775 | 0.579 | 0.795 |
| LLM decomposed scope | 0.699 | 0.427 | 0.717 |
| LLM decomposed diverse | 0.690 | 0.566 | 0.770 |

## LLM Decomposition Comparison

| Run | Scope metadata/filter | Fusion strategy | Hit@10 | Group Recall@10 | MRR | Single Hit@10 | Multi Hit@10 | Misleading Hit@10 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Original LLM decomposed | partial/earlier index | plain global RRF | 0.679 | 0.730 | 0.654 | 0.714 | 0.733 | 0.500 |
| LLM decomposed scope | yes | plain global RRF | 0.736 | 0.791 | 0.625 | 0.857 | 0.533 | 0.700 |
| LLM decomposed diverse | yes | subquery coverage + global RRF fill | 0.736 | 0.805 | 0.670 | 0.893 | 0.467 | 0.700 |

Notes:

- Adding `year_scope` / `department_scope` improved overall Hit@10 and helped `single-fact` / `misleading-single-fact`.
- Multi-fact Hit@10 dropped after scope filtering, mostly because final top-10 selection can still lose one required evidence group.
- Coverage-aware fusion improved overall Group Recall@10 and MRR, but did not improve multi-fact Hit@10 in this run.
- Planner output is not cached in these full runs, so LLM planner nondeterminism can affect exact case-level deltas. A stricter fusion-only comparison should cache subqueries first.

## Main Observations

### Dense And Hybrid

- Dense@50 shows that many missing answers are already in a larger candidate pool:
  - Overall Hit@50: 0.849
  - Overall Group Recall@50: 0.928
  - Single-fact Hit@50: 1.000
  - Multi-fact Hit@50: 0.667
- Hybrid pool50 final10 is the strongest non-LLM retriever in this round:
  - Overall Hit@10: 0.717
  - Overall Group Recall@10: 0.836
  - Overall MRR: 0.722
- Hybrid pool50 final50 does not improve Hit@50 over dense@50 overall, but it improves early ranking and multi-fact final@10 compared with dense/hybrid@10.

### Metadata Scope Filtering

- The current index records contain `year_scope` and `department_scope` for every chunk in `2026-04-25.001`.
- Planner output and retrieval filter are intentionally decoupled:
  - Planner always emits `year_scope` and `department_scope`.
  - Retriever only turns concrete scopes into filters.
  - `all` means no restriction on that dimension.
- For concrete scopes, retriever filters include both the concrete value and `all`, for example:

```python
{
    "year_scope": {"$in": ["112", "all"]},
    "department_scope": {"$in": ["3030", "all"]},
}
```

This keeps generally applicable FAQ or policy chunks visible while narrowing year/department-specific evidence.

### LLM Decomposed Retriever

- Planner-generated subqueries are generally reasonable.
- Scope filtering helped annual policy comparisons, for example:
  - Economics dual-degree eligibility, academic year `111` vs `112`
  - Economics dual-degree eligibility, academic year `113` vs `114`
  - Whether full-year CSIE/Economics courses in academic year `113` count toward graduation credits
- Remaining misses are often not caused by bad year/department scopes. Common patterns:
  - Query asks for a course list, but final top-10 contains individual `required_course` chunks instead of `required_courses_list`.
  - Multi-fact questions need evidence diversity across subqueries; plain RRF can let one subquery dominate final top-k.
  - Some misleading questions need contrast evidence from another department, but planner currently follows the explicit department in the query.

## Case-Level Changes For Coverage-Aware Fusion

Changed cases compared with `llm-decomposed-dense10-sparse10-final10`:

| Case | Type | Plain RRF | Diverse fusion | Question (translated) |
|---|---|---|---|---|
| `single-fact-013` | single | miss / GR 0.00 | hit / GR 1.00 | What are the second-year required courses for Economics students admitted in academic year 114? |
| `multi-fact-compare-001` | multi | miss / GR 0.50 | hit / GR 1.00 | How do credit requirements differ between a dual degree and a minor? |
| `multi-fact-compare-002` | multi | hit / GR 1.00 | miss / GR 0.75 | How do the Economics dual-degree eligibility rules differ between academic years 111 and 112? |
| `multi-fact-compare-003` | multi | hit / GR 1.00 | miss / GR 0.75 | How do the Economics dual-degree eligibility rules differ between academic years 113 and 114? |
| `multi-fact-compare-004` | multi | miss / GR 0.50 | miss / GR 0.00 | Which required courses do CSIE and Economics share in academic year 114? |
| `multi-fact-compare-005` | multi | miss / GR 0.00 | miss / GR 0.50 | How do first-year Economics required courses differ between academic years 111 and 112? |
| `multi-fact-compare-011` | multi | miss / GR 0.75 | miss / GR 0.50 | Overview of CSIE required courses for all years, academic year 113 |

Interpretation:

- Evidence diversity helps some cases where one subquery was previously underrepresented.
- The current quota is still crude. It improves coverage/MRR overall, but may demote high-quality global RRF hits in some annual policy comparisons.
- A more rigorous next experiment should fix planner output via cache and compare only fusion algorithms.

## Generated Reports

| Report | Path |
|---|---|
| Dense@10 | `data/eval_runs/retrieval_dense_scope_20260425.json` |
| Hybrid@10 | `data/eval_runs/retrieval_hybrid_rrf_scope_20260425.json` |
| Dense@50 | `data/eval_runs/retrieval_dense_top50_scope_20260425.json` |
| Hybrid pool50 final10 | `data/eval_runs/retrieval_hybrid_rrf_pool50_final10_scope_20260425.json` |
| Hybrid pool50 final50 | `data/eval_runs/retrieval_hybrid_rrf_pool50_final50_scope_20260425.json` |
| LLM decomposed scope | `data/eval_runs/retrieval_llm_decomposed_scope_20260425.json` |
| LLM decomposed diverse | `data/eval_runs/retrieval_llm_decomposed_diverse_scope_20260425.json` |
| Planner-only sample | `data/eval_runs/retrieval_llm_decomposed_plans_sample_20260425.json` |

## Recommended Next Step

Freeze planner output before the next fusion experiment. This will separate two effects:

1. Planner quality and nondeterminism.
2. Fusion/evidence-selection behavior.

After planner caching, compare:

- plain global RRF
- coverage-aware RRF
- coverage-aware RRF with a softer quota
- per-subquery top-N then global fill

