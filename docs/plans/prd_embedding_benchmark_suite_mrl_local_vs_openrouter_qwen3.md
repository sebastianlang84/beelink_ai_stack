# PRD: Embedding Benchmark Suite — MRL Truncation + Local CPU vs OpenRouter Qwen3

## 1) Ziel
Ein reproduzierbares Benchmark-Tool, das **Retrieval-Qualität** und **Performance/Latency** für Embeddings vergleicht:

1. **MRL vs. nicht-MRL Reduktion** (innerhalb desselben Qwen3-Modells)
2. **Lokales CPU-optimiertes Embedding-Modell** vs. **Qwen3-Embedding-8B via OpenRouter**

Wichtig: Muss **inkrementell** laufen können (nicht alles gleichzeitig), aber das Framework soll beide Testarten unterstützen.

---

## 2) Entscheidungsfragen

### 2.1 MRL / Dimension-Reduktion
- Welche `target_dim` ist der beste Tradeoff (z. B. 2048 vs 1024)?
- Ist **Prefix-Slicing (MRL)** messbar besser als eine **klassische Reduktion** auf dieselbe Dim?
- Welchen Einfluss hat **L2-Normalisierung nach Reduktion** auf Qualität/Portabilität?

### 2.2 Local vs Remote (OpenRouter)
- Wie stark unterscheiden sich **Embedding-Latenz** (p50/p95), **Throughput**, **Kosten** und **Retrieval-Qualität** zwischen:
  - Local CPU-optimiertem Modell (z. B. ONNX/Quantized)
  - Qwen3-Embedding-8B via OpenRouter
- Ist Local „gut genug“ (Qualität) für euren Doc/RAG-Usecase bei deutlich besserer Latenz/Kosten?

---

## 3) Nicht-Ziele
- Kein Benchmark der LLM-Antwortqualität (nur Retrieval).
- Keine Optimierung von Index-Hyperparametern (HNSW etc.) außer konstanten Defaults.
- Kein Multi-Provider-Vergleich (nur OpenRouter Qwen3 + Local).

---

## 4) Scope / Phasen

### Phase A — MRL vs nicht-MRL (Qwen3 only)
- Baseline: **native_dim** (keine Reduktion)
- MRL: **Prefix-Slicing** auf `target_dim`
- Nicht-MRL (Kontrolle): Reduktion auf `target_dim` via **PCA** (oder Random Projection als Fallback)
- Optional: (nur zur Diagnose) „falsches Slicing“: zufällige Dimensionen statt Prefix

### Phase B — Local CPU vs OpenRouter
- Local Embedder (CPU): engine wählbar (`sentence-transformers`, `onnxruntime`, optional `int8`/`quantized`)
- Remote Embedder: Qwen3-Embedding-8B via OpenRouter
- Vergleich pro Konfiguration:
  - Retrieval-Metriken
  - Timing-Metriken (Embedding + Query)
  - Resource-Metriken (CPU/RAM lokal)
  - Optionale Kosten-Metrik (Remote)

Beide Phasen sollen mit derselben CLI/Config ausführbar sein.

---

## 5) Datenmodell / Inputs

### 5.1 Corpus
- `corpus.jsonl`: `{ "doc_id": "...", "text": "...", "meta": { ... } }`

### 5.2 Queries
- `queries.jsonl`: `{ "query_id": "...", "text": "..." }`

### 5.3 Relevanz (Ground Truth)
- `qrels.jsonl`: `{ "query_id": "...", "relevant": ["doc_id1", "doc_id2"] }`

Fallback (wenn kein Gold-Labeling):
- Weak labels + klare Kennzeichnung im Report (geringere Aussagekraft)

---

## 6) Erfolgsmetriken

### 6.1 Retrieval (primär)
- Recall@K (K=1,5,10,20)
- MRR@10
- nDCG@10

### 6.2 Timing (primär für Phase B)

**Embedding:**
- Latenz pro Text: p50/p95
- Throughput: docs/sec (bei definierter Batchgröße & Concurrency)

**Retrieval:**
- Query-Latenz p50/p95

### 6.3 Ressourcen (lokal)
- CPU-Auslastung (optional: avg/max)
- RAM Peak

### 6.4 Storage
- Vektorgröße: `dim * 4` Bytes (float32) + Index-Overhead
- Collection/Index Größe on disk

### 6.5 Kosten (remote)
- Optionale Kostenabschätzung anhand Provider-Abrechnung (falls verfügbar) oder nur „API Calls“ zählen.

---

## 7) Experiment-Matrix

### 7.1 Remote Qwen3
- Modell: `qwen/qwen3-embedding-8b`
- Dims: `[native, 2048, 1024, 768, 512]`
- Normalisierung: `[true, false]` (default true)

### 7.2 Reduktionstypen (Phase A)
Für jede `target_dim`:
- `reducer = none` (nur wenn `target_dim == native_dim`)
- `reducer = mrl_prefix` (Prefix-Slice)
- `reducer = pca` (train PCA auf Sample des Corpus; dann project)
- `reducer = random_projection` (Fallback, falls PCA zu schwer)

### 7.3 Local CPU Modelle (Phase B)
Konfigurierbar, mindestens zwei Presets:
- **Small/fast bilingual** (Deutsch/Englisch): z. B. ein „small“ Multilingual SentenceTransformer
- **Medium** (falls CPU noch ok): bessere Qualität, höhere Latenz

Hinweis: konkreter Modellname soll rein in der Config stehen, damit leicht austauschbar.

---

## 8) Architektur

### 8.1 Komponenten
1) **Dataset Loader**
- Lädt `corpus/queries/qrels`
- Validiert IDs und Größen

2) **Embedder Interface**
- `embed_texts(texts: list[str]) -> list[list[float]]`
- Implementierungen:
  - `OpenRouterEmbedder` (OpenAI-compatible endpoint)
  - `LocalEmbedder` (sentence-transformers / onnxruntime)

3) **Reducer Interface**
- `fit(vectors_sample)` (optional)
- `transform(vectors) -> reduced_vectors`
- Implementierungen: `MRLPrefixReducer`, `PCAReducer`, `RandomProjectionReducer`

4) **Index Backend**
- Qdrant (primär) oder In-Memory (optional)
- Pro Konfiguration separate Collection/Index (keine Misch-Dimensionen)

5) **Runner**
- Build Index
- Query & retrieve Top-K
- Compute metrics
- Timing instrumentation

6) **Reporting**
- CSV + Markdown Summary
- Optional Plots

### 8.2 Timing-Instrumentierung (Pflicht)
- Jede Stage misst:
  - `embed_corpus_time`
  - `index_build_time`
  - `embed_queries_time`
  - `retrieval_time`
- Zusätzlich p50/p95 pro Embedding-Call (und optional pro Query)

### 8.3 Reproduzierbarkeit
- `runs/<ts>/config_resolved.yaml`
- `runs/<ts>/env.txt` (python version, pip freeze)
- `runs/<ts>/seed.txt` (random seed)

---

## 9) CLI / UX
Ein Command, mehrere Modes:

- Phase A:
  - `python -m emb_bench run --config config.yaml --phase mrl`

- Phase B:
  - `python -m emb_bench run --config config.yaml --phase local_vs_remote`

Optional:
- `--subset_docs N` für schnelle Iteration
- `--subset_queries M`
- `--warmup 20` (Warmup Calls)
- `--concurrency 1|2|4` (Remote respektiert Rate Limits)

---

## 10) Konfigurationsschema (config.yaml)

```yaml
phases: ["mrl", "local_vs_remote"]  # einzeln oder beide

openrouter:
  base_url: "https://openrouter.ai/api/v1"
  api_key_env: "OPENROUTER_API_KEY"
  timeout_s: 30
  max_retries: 5
  rpm_limit: 120

remote_model:
  name: "qwen/qwen3-embedding-8b"
  native_dim: 4096

mrl_phase:
  dims: [4096, 2048, 1024]
  reducers: ["mrl_prefix", "pca"]
  normalize: true
  pca:
    sample_size: 5000
    whiten: false

local_phase:
  local_embedders:
    - id: "local_fast"
      engine: "onnxruntime"      # or: "sentence_transformers"
      model: "<HF_OR_LOCAL_MODEL_NAME_OR_PATH>"
      batch_size: 64
      threads: 8
    - id: "local_quality"
      engine: "sentence_transformers"
      model: "<HF_OR_LOCAL_MODEL_NAME_OR_PATH>"
      batch_size: 32
      threads: 8
  compare_against_remote: true
  remote_dims: [4096, 2048, 1024]
  remote_reducer: "mrl_prefix"
  normalize: true

dataset:
  corpus_path: "data/corpus.jsonl"
  queries_path: "data/queries.jsonl"
  qrels_path: "data/qrels.jsonl"

backend:
  type: "qdrant"
  qdrant:
    url: "http://localhost:6333"
    distance: "cosine"

retrieval:
  top_k: 20

runtime:
  seed: 42
  subset_docs: null
  subset_queries: null
  warmup_calls: 20
  concurrency: 2

report:
  output_dir: "runs"
  make_plots: true
```

---

## 11) Akzeptanzkriterien (Definition of Done)
- Läuft end-to-end für Phase A **und** Phase B (separat).
- Report enthält:
  - Ranking der Konfigurationen nach nDCG@10 und Recall@10
  - Relative Deltas vs Baseline (remote native_dim)
  - Timing p50/p95 + Throughput
  - Storage-Schätzung
  - Empfehlung: `target_dim` und „local vs remote“ Entscheidung (mit Daten)
- Fail-fast bei Dimension-Mismatch und fehlenden qrels.

---

## 12) Risiken & Mitigations
- **Kosten/Rate Limits remote:** Caching + subset mode + concurrency-limit.
- **PCA Fit teuer:** PCA nur auf Sample; Random Projection als Fallback.
- **Local Performance schwankt:** Warmup + fixed threads/batch + isolierter Run.
- **Weak labels:** Gold-Set priorisieren (mind. 100 Queries manuell kuratiert).

---

## 13) Implementationshinweise für Codex
Repo-Struktur (Vorschlag):
- `emb_bench/`
  - `run.py`
  - `dataset.py`
  - `embedders/openrouter.py`
  - `embedders/local.py`
  - `reducers/mrl_prefix.py`
  - `reducers/pca.py`
  - `reducers/random_projection.py`
  - `index/qdrant_backend.py`
  - `metrics.py`
  - `report.py`
- `data/`
- `runs/`

Dependencies minimal:
- `numpy`, `pyyaml`, `tqdm`
- `qdrant-client` (wenn Qdrant)
- `scikit-learn` (PCA) — optional (nur Phase A mit PCA)
- `sentence-transformers` und/oder `onnxruntime` (local)
- `matplotlib` (optional)
