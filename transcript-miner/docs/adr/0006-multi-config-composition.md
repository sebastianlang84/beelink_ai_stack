# ADR 0006: Multi-Config (Config Composition) — Semantik, Konfliktregeln, Run-Namespaces

Status: **Accepted**

## Intent

Eine präzise, deterministische **Doku-/Design-Spezifikation** für Runs mit **mehreren YAML-Configs** definieren, ohne bestehende Implementierung (Single-Config) zu verändern.

## Problem

Wir wollen mehrere YAML-Configs kombinieren (z.B. Topic-spezifische Sets) und dabei drei unterschiedliche Zielbilder sauber unterscheiden:

1. **Merge**: mehrere YAMLs zu *einer* effektiven Config zusammenführen.
2. **Multi-Run**: mehrere YAMLs *getrennt* ausführen, aber später *gemeinsam analysieren*.
3. **Union**: bestimmte Felder (z.B. Channels, Keywords) vereinigen, Rest konfliktauflösend.

Dabei müssen wir:

- deterministische Konfliktregeln (Tie-Breaking) dokumentieren,
- Run-Identität/Namespaces sauber definieren (keine stillen Overwrites; Policy: [`AGENTS.md`](../../../AGENTS.md:140)),
- die bestehende Prioritätshierarchie **unverändert** lassen: CLI > Config > Env > Defaults (siehe [`docs/config.md`](../config.md:11) und Pattern [`AGENTS.md`](../../../AGENTS.md:166)),
- und das CLI nur als **Entwurf** beschreiben (keine erfundenen Ist-Flags).

## Kontext / Evidenz (Ist-Zustand)

- Offene Backlog-Stellen: Semantik/Katalog [`TODO.md`](../../../TODO.md:105), CLI-Konzept [`TODO.md`](../../../TODO.md:117), Run-Namespaces [`TODO.md`](../../../TODO.md:121), Output-Pfad-Policy Empfehlung [`docs/config.md`](../config.md:120).
- Primärer Modul-Entry ist [`transcript_miner.main.parse_arguments()`](../../src/transcript_miner/main.py:229) (aktuell: optionales positional `config_path` + `--api-key`).
- Relative Pfade in `output.*`/`logging.*` werden beim Laden relativ zum Config-Verzeichnis aufgelöst (Evidenz/ADR: [`docs/adr/0005-output-path-resolution.md`](0005-output-path-resolution.md:17)).

## Begriffe und deterministische Ordnung

### ConfigFile

Ein YAML-File (Pfad auf Disk), das (wie heute) via Loader geladen und validiert wird.

### ConfigSet

Eine Menge mehrerer `ConfigFile`-Pfade.

### Kanonische Config-Order (Determinismus)

Für alle Modi, die eine Reihenfolge benötigen (Merge/Tie-Breaking, stable Union-Order), definieren wir eine **kanonische Order**:

1. Pfade werden zu `absolute_path = Path(path).resolve()` normalisiert.
2. Duplikate (gleicher `absolute_path`) werden entfernt.
3. Sortierung lexikographisch nach dem String der `absolute_path`.

Diese Regel macht das Ergebnis unabhängig von der Argument-Reihenfolge und damit deterministisch.

## Modus-Katalog (Spezifikation)

### Modus A: Merge (eine effektive Config)

**Ziel:** aus mehreren YAMLs eine effektive Config erzeugen und dann einen *einzigen* Miner-Run starten.

**Semantik (normativ):**

- Merge ist ein **Deep-Merge** von Objekten/Maps.
- Für Listen und Scalars gilt die feldspezifische Regel-Tabelle (unten).
- Konflikte werden deterministisch gelöst (kanonische Order).

**Einsatz:** wenn mehrere Files nur „Overrides“ sind (z.B. ein Basisset + ein kleines Topic-Delta).

### Modus B: Multi-Run (mehrere Runs, gemeinsame Analyse)

**Ziel:** jede Config *separat* ausführen (eigene Output-/Logging-Settings), danach Analyse über **Union der Output-Roots**.

**Semantik (normativ):**

- Pro ConfigFile entsteht ein eigener „Child Run“.
- Jeder Child Run nutzt seine eigene `output.*`/`logging.*` Konfiguration.
- Die gemeinsame Analyse referenziert eine definierte **ConfigSet-Run-ID** (siehe „Run-Identität“).

**Einsatz:** wenn Configs unterschiedliche Output-/Logging-/Download-Parameter bewusst getrennt halten sollen.

### Modus C: Union (vereinigen + konfliktauflösen)

**Ziel:** ein einzelner Miner-Run, bei dem bestimmte Felder (Channels/Keywords/Sprachen) vereinigt werden, während andere deterministisch konfliktauflösend sind.

**Semantik (normativ):**

- „Union-Felder“ werden zusammengeführt (stable, dedupliziert).
- Andere Felder werden wie im Merge-Modus konfliktauflösend behandelt (oder fail-fast).

**Einsatz:** wenn man mehrere Topic-Configs zu einem „Superset Run“ machen möchte.

## Feld-Semantik & Konfliktregeln (normativ)

Die folgenden Regeln gelten **zusätzlich** zur unveränderten Prioritätshierarchie (CLI > Config > Env > Defaults, siehe [`docs/config.md`](../config.md:11)). In Multi-Config betreffen sie ausschließlich die Auflösung *zwischen* mehreren ConfigFiles.

> Notation: „C1 … Cn“ sind Configs in **kanonischer Order**.

### 1) `output.*` (Kollisionskritisch)

Begründung: `output.*` bestimmt den Ort von `progress.json`, `transcripts/` etc. (siehe Output-Referenz in [`README.md`](../../README.md:241)); Kollisionen sind Datenverlust-/Inconsistency-Risiko.

**Regel (Merge/Union): fail-fast bei Konflikt.**

- Wenn mindestens eine Config `output.global`/`output.global_root` **oder** `output.topic` setzt, dann müssen in **allen** Configs die effektiven Werte von
  - `output.global` (bzw. `output.global_root` als Alias)
  - `output.topic`
  - `output.metadata`
  - `output.retention_days`
  **identisch** sein.
- Sonst (Legacy): wenn mindestens eine Config `output.root_path` oder `output.path` setzt, müssen in **allen** Configs die effektiven Werte von
  - `output.root_path` (falls gesetzt) bzw. `output.path` (fallback)
  - `output.use_channel_subfolder`
  - `output.metadata`
  - `output.retention_days`
  **identisch** sein.
- Andernfalls: **Fehler** („output.* conflict“).

**Tie-Breaking (deterministisch):**

- Für die Fehlerausgabe wird als „Referenz“ deterministisch C1 verwendet.

**Regel (Multi-Run): pro Config.**

- Keine Gleichheitsanforderung; jede Config schreibt in ihre eigenen Outputs.

### 2) `logging.*` (Kollisionskritisch)

Begründung: mehrere Runs in dieselben Logfiles führen zu schwer auditierbaren, nicht-deterministischen Log-Interleavings.

**Regel (Merge/Union): fail-fast bei Konflikt.**

- `logging.level`, `logging.file`, `logging.error_log_file` müssen über alle Configs identisch sein.
- (Optional vorhandene Rotation-Felder sind analog zu behandeln: siehe Schema-Felder in [`docs/config.md`](../config.md:184)).

**Tie-Breaking (deterministisch):**

- Referenz ist C1; Abweichungen führen zu Fehler.

**Regel (Multi-Run): pro Config.**

- Jede Config loggt in ihre eigenen Files.

### 3) `youtube.num_videos` (Skalierung/Quota)

**Merge:**

- Konfliktregel: **last-one-wins** in kanonischer Order.
  - Effektivwert = Wert aus Cn, falls dort gesetzt.
  - Motivation: Merge ist ein Override-Mechanismus.

**Union:**

- Konfliktregel: **Maximum** über alle gesetzten Werte.
  - Effektivwert = `max(num_videos_i)`.
  - Motivation: Union soll den „Superset“-Scope abdecken.

**Multi-Run:**

- Pro Config der jeweilige Wert.

### 4) `youtube.preferred_languages` (Transcript-Auswahl)

Evidenz zum Ist-Verhalten der Liste: [`docs/config.md`](../config.md:77).

**Merge:**

- Konfliktregel: **last-one-wins** in kanonischer Order.

**Union:**

- Konfliktregel: **stable union** (deterministisch, dedupliziert).
  - Startliste = `preferred_languages` aus C1.
  - Dann für C2..Cn: append aller Einträge, die noch nicht enthalten sind (Vergleich: exact string nach `strip()`).

**Multi-Run:**

- Pro Config der jeweilige Wert.

### 5) Felder, die „vereinigt“ werden (Union-Felder)

Diese Felder werden in **Union** explizit zusammengeführt; in **Merge** gilt die jeweilige Merge-Regel (i.d.R. last-one-wins) und in **Multi-Run** per Config.

| Feld | Union-Regel | Dedupe-Kriterium | Stabilität |
|---|---|---|---|
| `youtube.channels` | stable union | exact string nach `strip()` | kanonische Order C1..Cn, dann first-seen |
| `youtube.keywords` | stable union | exact string nach `strip()` | kanonische Order C1..Cn, dann first-seen |
| `youtube.preferred_languages` | stable union | exact string nach `strip()` | siehe oben |

Hinweis:

- Keine zusätzliche „Handle-Normalisierung“ wird in der Union-Spezifikation erzwungen; die Pipeline akzeptiert Handles/URLs/IDs. Die Handle-Normalisierung ist heute primär eine Output-Path-Sanitization (siehe Pattern in [`docs/config.md`](../config.md:168)).

### 6) Alle anderen Felder

**Regel (normativ):**

- In Merge/Union gilt: **fail-fast bei Konflikt**, wenn das Feld nicht explizit in den Regeln oben oder in einer späteren Ergänzung dieses ADRs erfasst ist.

Motivation:

- verhindert implizite, schwer nachvollziehbare Semantik,
- schützt gegen stille Änderungen an Analyse-Prompts/Outputs,
- hält Doku und spätere Implementierung eng gekoppelt.

## Run-Identität / Namespaces (deterministisch)

### Ziel

- Ein Multi-Config Run braucht eine stabile, deterministische Identität, die aus den ConfigFiles ableitbar ist.
- Re-Runs dürfen keine stillen Overwrites erzeugen (Policy: [`AGENTS.md`](../../../AGENTS.md:140)).

### ConfigSet-ID (Spezifikation)

Wir definieren eine `config_set_id` als String:

1. `names_part`:
   - Nimm die Basenames der ConfigFiles (ohne Extension), in kanonischer Order.
   - „Join“ mit `+`.
   - Beispiel: `config_investing.yaml` + `config_ai_knowledge.yaml` → `config_investing+config_ai_knowledge`.
2. `hash_part`:
   - Berechne SHA-256 über die Bytes der ConfigFiles in kanonischer Order, getrennt durch ein Null-Byte (`\0`).
   - Nimm z.B. die ersten 12 hex chars als Kurzform.
3. `config_set_id = {names_part}__cs-{hash_part}`.

**Eigenschaften:**

- deterministisch (gleiche Files → gleiche ID),
- kollisionsarm (Hash),
- menschlich interpretierbar (names_part).

### Namespace-Verwendung (Policy)

**Normative Policy:**

- Für Artefakte, die einen Multi-Config Kontext repräsentieren (z.B. „gemeinsame Analyse“), wird ein eigener Namespace-Ordner verwendet:
  - empfohlen: `<repo>/output/_runs/{config_set_id}/...`
- Dieser Ordner darf **nicht** implizit überschrieben werden.
  - Wenn er existiert: der Run muss mit einem klaren Fehler abbrechen, **oder** es muss explizit ein „Overwrite/Reuse“-Mechanismus gewählt werden (CLI-Entwurf, siehe unten).

**Hinweis zur Pfad-Policy:**

- Relative Pfade sind Config-dir-relativ (siehe [`docs/adr/0005-output-path-resolution.md`](0005-output-path-resolution.md:70)). Für Configs unter [`config/`](../../config:1) ist deshalb `../output/_runs/...` zu verwenden.

### Re-Runs (ohne stille Overwrites)

Zwei zulässige Strategien (Design-Optionen; keine Implementierung hier):

1. **Fail-fast default**: existierender `{config_set_id}`-Ordner → Abbruch.
2. **Explizites Reuse/Overwrite** (Entwurf): Nutzer muss explizit zustimmen (z.B. Draft-Flag `--overwrite-run-root` oder `--reuse-run-root`).

## CLI-Konzept (Entwurf; keine Implementierung)

### Ausgangslage

- Modul-CLI akzeptiert heute ein optionales positional `config_path` (siehe [`transcript_miner.main.parse_arguments()`](../../src/transcript_miner/main.py:229)).

### Ziel (Entwurf)

Mehrere Configs sollen angebbar sein, ohne das Single-Config Verhalten zu brechen.

#### Entwurf A (Modul): positional „nargs=+“

- Ändere `config_path` → `config_paths` mit `nargs='+'` in [`transcript_miner.main.parse_arguments()`](../../src/transcript_miner/main.py:229).
- Backward kompatibel für 1 Config.
- Nachteil: erschwert „optional config“ Nutzung ohne Config (heute `default=None`).

#### Entwurf B (Modul): neues repeatable `--config` + optional positional bleibt

- Füge `--config <path>` hinzu (repeatable), während positional weiter für 1 Config bleibt.
- Regel: wenn `--config` verwendet wird, darf kein positional config gesetzt sein (und umgekehrt) → klare Fehler.

#### Entwurf (Modus-Auswahl)

- Füge einen Modus-Schalter hinzu (z.B. Draft: `--config-mode {merge,union,multi-run}`).
- Default-Empfehlung: **multi-run**, da es die geringste Kollisionsgefahr hat.

> Wichtig: Alle CLI-Flags in diesem Abschnitt sind **Entwurf** und existieren nicht notwendigerweise im aktuellen Code.

## Beispiele (nur Design; referenziert vorhandene Configs)

### Multi-Run (Empfehlung als Default)

Inputs:

- [`config/config_investing.yaml`](../../config/config_investing.yaml:1)
- [`config/config_ai_knowledge.yaml`](../../config/config_ai_knowledge.yaml:1)

Entwurf:

```bash
# Draft: mehrere Configs + multi-run
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml \
  --config-mode multi-run
```

### Union

Entwurf:

```bash
uv run python -m transcript_miner \
  --config config/config_investing.yaml \
  --config config/config_ai_knowledge.yaml \
  --config-mode union
```

## Entscheidung

Wir dokumentieren **alle drei Modi** und definieren konservative, deterministische Regeln:

- Kollisionskritische Pfade/Logs sind in Merge/Union **fail-fast**,
- Union-Felder sind explizit benannt und stable-union,
- alle nicht spezifizierten Felder sind in Merge/Union **fail-fast**, bis sie explizit geregelt sind,
- Multi-Run ist die „sichere“ Default-Empfehlung.

## Konsequenzen

- Implementierung kann später schrittweise erfolgen, ohne dass Doku-Semantik „hinterherhinkt“.
- Der fail-fast Ansatz zwingt explizite Entscheidungen für riskante Felder (Outputs/Logs/Analyse-Prompts).
- Für echte Multi-Config UX ist ein klarer Run-Root Namespace nötig (Policy oben).

## Offene Punkte

- Welche „anderen Felder“ sollen später Union- oder Merge-Semantik bekommen (z.B. Analyse-Config unter `analysis.*`)?
- Wie genau wird die gemeinsame Analyse im Multi-Run Modus getriggert (z.B. Auswahl der Output-Roots)?
