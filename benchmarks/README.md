# Benchmarks

This directory holds the comparison harness. It does not hold published results
yet — nothing here has been measured against a real model, and the tables below
are empty on purpose.

## What a benchmark run has to fix before its numbers mean anything

1. **Scenario versions.** Every row must come from the same corpus commit.
2. **Adapter configuration.** Recorded in each result as `adapter_fingerprint`.
3. **Trial count.** One trial per scenario says nothing about variance.
4. **App profile.** The only thing that should differ between the two baseline
   rows.
5. **Denominators.** Errors and timeouts leave the denominator and are reported
   separately. Scores from different denominators are not comparable.

## The two required baselines

| Configuration | What it is |
|---|---|
| Vulnerable mock | Authorization decided from a model-supplied `as_user` argument. One documented defect. |
| Hardened mock | The same application with authorization enforced against the authenticated principal. |

## Running the comparison

```bash
uv run promptfence compare scenarios/ --output results/comparison.jsonl
```

Both profiles run the same scenarios, in the same process, with the same adapter
and the same trial count. The command exits 1 if the vulnerable side is not
detected — a comparison where nothing was found on either side is a broken
harness, not a good result.

## Published results

None yet. When a result set is published, commit it here with:

- the corpus commit hash,
- the runner version and `uv.lock`,
- the adapter fingerprint and, for remote runs, the model id,
- the raw JSONL,
- the command used,
- hardware and timing context,
- known limitations and excluded trials.

Do not fill a table in from a single convenient run. A benchmark whose claims
cannot be falsified is not a benchmark.

## Reproducing a published run

```bash
git checkout <corpus-commit>
uv sync --frozen --all-groups
uv run promptfence compare scenarios/ --output results/comparison.jsonl
diff <(jq -S . results/comparison.jsonl) <(jq -S . baselines/<name>.jsonl)
```

Model-dependent runs will not reproduce exactly — they are stochastic. The
mock-adapter baselines must, byte for byte apart from the `run_id` and timings.
