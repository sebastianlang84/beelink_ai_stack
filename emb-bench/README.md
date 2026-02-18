# emb-bench — Embedding Benchmark Suite

Benchmarks für:
- Phase A: MRL Prefix-Slicing vs PCA/Random-Projection (Qwen3 remote)
- Phase B: Local CPU vs OpenRouter remote (Qwen3)

PRD: `docs/plans/prd_embedding_benchmark_suite_mrl_local_vs_openrouter_qwen3.md:1`

## Quickstart (Docker, empfohlen)

1) Config anlegen (Beispiel):
- `emb-bench/config.example.yaml`
- `emb-bench/config.local_only.yaml` (ohne OpenRouter; nur lokale Embeddings)

2) Run (empfohlen via Wrapper, setzt `DOCKER_UID/DOCKER_GID` korrekt):
```bash
cd /home/wasti/ai_stack
./scripts/run_emb_bench.sh --env-file .env -- \
  python -m emb_bench run --config config.example.yaml --phase mrl --subset-docs 50 --subset-queries 10
```

Local-only smoke (ohne Remote/API-Key):
```bash
cd /home/wasti/ai_stack
./scripts/run_emb_bench.sh -- \
  python -m emb_bench run --config config.local_only.yaml --phase local_vs_remote
```

3) Outputs:
- `emb-bench/runs_out/<ts>/report.md`
- `emb-bench/runs_out/<ts>/results.csv`

## Hinweise
- Remote benötigt `OPENROUTER_API_KEY` in `.env`.
- Local Modelle laden ggf. Model-Files aus dem Netz (HF/fastembed).
