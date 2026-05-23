# Published benchmark baselines

Nothing published yet.

A baseline is committed here only when it has been reproduced from a clean
checkout. Each file is the raw JSONL from `promptfence compare`, plus a
`metadata.json` recording:

```json
{
  "corpus_commit": "<git sha>",
  "runner_version": "0.1.0",
  "uv_lock_sha256": "<sha256 of uv.lock>",
  "adapter": "mock",
  "adapter_fingerprint": null,
  "command": "uv run promptfence compare scenarios/ --output results/comparison.jsonl",
  "trials_per_scenario": 1,
  "host": "<uname -a>",
  "notes": "Deterministic mock adapter. Two runs are identical apart from run_id and duration_ms."
}
```

Baselines are evidence, not decoration. Do not regenerate one to make a change
look good — if a change alters the baseline, the change is the finding, and it
belongs in the commit that made it.
