# Cleanup / Konsolidierung (Plan + Status)

Ziel: Repo-Hygiene, weniger Duplikate, klarere Policies (Code, Doku, Artefakte). Dieses Dokument kombiniert Plan + Status.

## Leitplanken

- **Keine Secrets** ins Repo (siehe `README.md`).
- **Keine stillen Overwrites**: bei Cleanup-Aktionen immer explizit dokumentieren.
- **Atomar** vorgehen: kleine PRs, jeweils mit klaren Checks.

## Entscheidungen (umgesetzt)

- `data/` ist komplett lokal und wird ignoriert (nichts aus `data/` wird getrackt).
- `docs/audit/cleanup_report.json` wird entfernt.
- `run.py` wird entfernt; Einstieg nur noch via `python -m transcript_miner`.
- `channel_mapping` Cache liegt standardmaessig unter `output/_cache/` (Legacy-Fallback bleibt).

## Kurzfazit (Status)

1) **Resolved: Audit-Artefakt mit machine-local Paths**  
   `docs/audit/cleanup_report.json` wurde entfernt; `docs/audit/*.json` ist jetzt lokal ignoriert.

2) **Resolved: `data/` Policy-Inkonsistenz**  
   `data/` ist nun vollständig lokal/ignored; getrackte Dateien wurden entfernt.

3) **Duplizierte Helper-Funktionen / Token-Counting**  
   `_normalize_channel_namespace` und `_canonicalize_symbol_key` existieren doppelt in:
   - `src/transcript_ai_analysis/aggregation_runner.py`
   - `src/transcript_ai_analysis/llm_report_generator.py`
   Außerdem hat `llm_report_generator.py` ein eigenes `estimate_tokens()`, während `common.utils.calculate_token_count()` bereits existiert.

4) **Cache/Artefakt liegt in `config/` (trotz ignore)**  
   `config/channel_mapping.json` ist ein Laufzeit-Cache (in `.gitignore`), wird aber als Default-Pfad im Code referenziert (`src/transcript_miner/channel_resolver.py`). Das ist konzeptionell inkonsistent: `config/` sollte „nur Konfig“ sein.

## Priorisierung (Empfehlung)

### P0 (low risk, hoher Nutzen)

1) **`docs/audit/cleanup_report.json` ent-noisen (erledigt)**
   - Datei aus dem Repo entfernt; Audit-Outputs werden ignoriert.

2) **`data/`-Policy (erledigt)**
   - `data/` ist lokal/ignored; getrackte Files wurden entfernt.

### P1 (mittel, überschaubar)

3) **Helper-Dedupe (ohne Behavior-Change)**
   - Gemeinsame Funktionen nach `src/common/` verschieben (z.B. `src/common/analysis_utils.py` oder `src/common/normalization.py`).
   - Beide Call-Sites auf den gemeinsamen Import umstellen.
   - Token-Counting: `estimate_tokens()` eliminieren und überall `calculate_token_count()` nutzen (oder umgekehrt), aber **nur einen Codepfad** behalten.

4) **`config/channel_mapping.json` aus `config/` herauslösen (konzeptionell)**
   - Ziel: Cache unter `output/` oder unter einem dedizierten Cache-Ordner (z.B. `output/_cache/`), nicht unter `config/`.
   - Übergang: alten Pfad noch lesen (fallback), neuen Pfad als Default schreiben.
   - Doku: in `docs/config.md` kurz erwähnen (wo Cache liegt, wie man ihn löscht).

### P2 (höherer Scope, optional)

5) **Tools konsolidieren**
   - `tools/generate_llm_report.py` vs. integrierte Pipeline: prüfen, ob Tool noch Mehrwert hat; sonst deprecate/move nach `docs/audit/` oder als „power user tool“ klar kennzeichnen.

## Artefakte / Generated Files (Vorschläge)

Diese Dinge sollten **nicht** im Git landen (vieles ist bereits ignoriert); Cleanup heißt hier primär: „lokal löschen wenn nötig“ + „Policy klar machen“.

- Python caches: `**/__pycache__/`, `*.pyc`
- Test/formatter caches: `.pytest_cache/`, `.ruff_cache/`
- Env/uv caches: `.venv/`, `.uv-cache/`
- Packaging build artefacts: `src/*.egg-info/`, `build/`, `dist/`
- Run artefacts: `output/` (bereits ignoriert), `logs/` (bereits ignoriert)

## Konkreter PR-Plan (falls wir es umsetzen)

**PR 1 (P0, nur Doku/Repo-Hygiene)**
- `data/`-Policy umgesetzt (lokal/ignored).
- `docs/audit/cleanup_report.json` entfernt + Audit-Outputs ignoriert.
- Optional: `docs/audit/README.md` mit „Audit-Dateien & Regeln“.

**PR 2 (P1, Code-Dedupe ohne Behavior Change)**
- Helper-Funktionen zentralisieren + Imports umstellen.
- Token-Counting vereinheitlichen.
- Tests/Smoke-Checks laufen lassen.

**PR 3 (P1/P2, Cache-Location & Tooling)**
- `channel_mapping` Cache-Pfad migrieren (fallback+deprecation).
- Tooling/Entry-Point Entscheidung dokumentieren, ggf. deprecations.

## Checks (für später, wenn Cleanup umgesetzt wird)

- `uv run pytest -q`
- `uv run python -m transcript_miner --help`
- `git status --porcelain`

## Offene Entscheidungen (bitte wählen, bevor wir PR 1 machen)

1) **`tools/generate_llm_report.py`**: behalten (Power-User-Tool) oder entfernen/deprecate?
