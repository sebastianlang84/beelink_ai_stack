# ADR 0005: Output-Pfad-Auflösung und Ablage-Policy (keine Outputs unter `config/`)

Status: **Accepted**

## Problem

Wir brauchen eine eindeutige, leicht merkbare Policy:

- **Wo** liegen Outputs standardmäßig?
- **Wie** werden relative Pfade in `output.*` interpretiert?
- Welche Ordner sind für welche Artefakte gedacht?

Ziel: Nutzer sollen nicht „aus Versehen“ unter [`config/`](../../config:1) schreiben.

## Kontext / Evidenz (Ist-Zustand)

### 1) Relative Pfade werden beim Config-Laden relativ zum Config-Verzeichnis aufgelöst

- `base_dir = config_path.parent.resolve()` in [`common.config.load_config()`](../../src/common/config.py:23)
- Pfadauflösung in [`common.path_utils.resolve_paths()`](../../src/common/path_utils.py:12) → [`common.path_utils._resolve_path()`](../../src/common/path_utils.py:90)

Konsequenz: Wenn eine Config unter [`config/`](../../config:1) liegt und dort `output.root_path: ../output/stocks` steht, wird daraus zunächst `<repo>/output/stocks`.

### 2) Der effektive Output-Pfad wird zusätzlich zur Laufzeit über `OutputConfig.get_path()` bestimmt

- Berechnung in [`OutputConfig.get_path()`](../../src/common/config_models.py:66)
- Channel-Subfolder-Name: `@` entfernen, `/` und `\\` → `_` (siehe [`OutputConfig.get_path()`](../../src/common/config_models.py:66))

Konsequenz: Es existieren aktuell zwei Stellen, an denen Pfade „relativ“ interpretiert werden (Loader + Runtime). Das erhöht die Gefahr von Überraschungen.

## Optionen

### Option A: Repo-Root-relativ (normativ)

**Policy:** Relative `output.*` Pfade werden als relativ zu „Repo-Root“ interpretiert.

**Pros**

- Erwartbar im Projektkontext („Outputs sind Projektartefakte“).
- `../output/...` wäre immer `<repo>/output/...`.

**Cons**

- Passt nicht zum aktuellen Loader-Verhalten (siehe [`common.config.load_config()`](../../src/common/config.py:23)).
- Würde ohne Code-Änderung in der Doku eine Semantik behaupten, die aktuell nicht zuverlässig gilt.

### Option B: Config-Dir-relativ + klare „Nie unter config“ Regel (normativ)

**Policy:** Relative `output.*` Pfade werden relativ zur Config-Datei interpretiert.

Zusätzlich:

- [`config/`](../../config:1) enthält **nur** Configs.
- Outputs werden so konfiguriert, dass sie **nicht** unter [`config/`](../../config:1) landen.

**Pros**

- Entspricht dem Ist-Verhalten des Loaders (siehe [`common.config.load_config()`](../../src/common/config.py:23)).
- Einfaches, „shell-logisches“ Modell: wie `../` vs. absolute Pfade.

**Cons**

- `../output/...` in Configs unter [`config/`](../../config:1) landet weiterhin unter `<repo>/output/...`.
- Erfordert, dass Beispiele/Docs konsequent `../output/...` nutzen.

## Entscheidung

Wir wählen **Option B**.

Normative Regeln:

1. Relative Pfade in `output.*` sind **relativ zur Config-Datei**.
2. [`config/`](../../config:1) ist ein reiner Config-Ordner: **keine Outputs** unterhalb dieses Verzeichnisses.
3. Wenn Outputs unter `<repo>/output/...` liegen sollen, muss in YAML explizit ein Pfad verwendet werden, der aus dem Config-Verzeichnis heraus „zurück“ springt, z.B. `../output/stocks` (oder ein absoluter Pfad).

## Konsequenzen

- Doku/Beispiele müssen `../output/<namespace>` bevorzugen, wenn Configs unter [`config/`](../../config:1) liegen.
- Multi-Channel: entweder `output.global` + `output.topic` **oder** `output.root_path` + `output.use_channel_subfolder: true`, sonst kollidieren `ingest_index.jsonl`/`transcripts` (Test: [`test_multi_channel_requires_root_path_and_channel_subfolder()`](../../tests/test_multichannel_output_validation.py:10)).

## Migration / How-to

- Wenn eine Config heute `output.root_path: ../output/stocks` nutzt und unter [`config/`](../../config:1) liegt:
  - **Ist-Effekt:** Outputs landen unter `<repo>/output/stocks/...` (siehe Loader-Evidenz oben).
  - **Soll (empfohlen, global layout):** setze `output.global: ../output` und `output.topic: stocks` (Alias: `output.global_root`).
  - **Legacy (falls gewünscht):** behalte `output.root_path` (ggf. plus `output.use_channel_subfolder: true`).
