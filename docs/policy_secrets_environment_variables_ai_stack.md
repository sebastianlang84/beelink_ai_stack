# Policy — Secrets & Environment Variables (ai_stack)

Stand: 2026-01-11

Ziel: **SSOT (Single Source of Truth)** für Secrets am Home-Server, ohne Secrets im Repo. Gleichzeitig: **Least Privilege** (jeder Service bekommt nur die Secrets, die er braucht).

---

## 0) Scope

Diese Policy gilt für:
- Docker Compose Stacks unter `/home/wasti/ai_stack/…`
- Services wie:
  - Open WebUI
  - Transcript Miner MCP Server (`mcp-transcript-miner`)
  - Qdrant, Traefik, SearXNG (falls vorhanden)

Nicht im Scope:
- Vollwertige Secret-Manager (Vault, AWS Secrets Manager, etc.).

---

## 1) Begriffe

- **Secret**: API Key, Token, Passwort, private Schlüssel.
- **SSOT (Single Source of Truth)**: zentrale Quelle für Secrets.
- **Least Privilege**: ein Container erhält nur die Secrets, die er zwingend benötigt.
- **Env File**: Datei im Format `KEY=value`, von Docker Compose mit `--env-file` eingelesen.

---

## 2) Harte Regeln (Do / Don’t)

### 2.1 Do

- **Keine Secrets im Repo-Verzeichnis** speichern.
  - Keine `secrets.env` unterhalb von `/home/wasti/ai_stack/…`.
- **SSOT ist `/etc/ai_stack/secrets.env`**.
- **Secrets-Dateien sind restriktiv**:
  - Rechte: `0600`
  - Owner: `root:root` (klassisch) **oder** `wasti:wasti` (privater Home-Server; entscheidend ist: kein World-/Group-Read)
- **Pro Stack nur minimal benötigte Secrets** weitergeben (Least Privilege).
- **Provider-Keys** (OpenAI/OpenRouter/etc.) nicht global an alle Container durchreichen, sondern nur dort, wo sie gebraucht werden.

### 2.2 Don’t

- Keine Secrets in:
  - Git
  - Dockerfiles
  - Logs
  - Screenshots/Chat
- Keine „ungefilterten“ Debug-Outputs teilen, die Env-Werte enthalten (z. B. `docker compose ... config`).
  - Safe: `docker compose ... config >/dev/null`
  - Wenn du Output teilen musst: `docker compose ... config | ./scripts/redact_secrets_output.sh`
- Keine globale Weitergabe der kompletten SSOT-Datei an alle Container.
  - „Ein File für alle Container“ ist bequem, aber bricht Least Privilege.

---

## 3) Ordnerstruktur (Server)

### 3.1 Zentrale Secrets (SSOT)

- `/etc/ai_stack/secrets.env`
  - enthält alle Secrets, die überhaupt existieren (SSOT)

Beispiel-Keys (nur als Liste, **keine Werte**):
- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY` (optional; für Tavily MCP / Doc Fetching)
- `YOUTUBE_API_KEY`
- `YOUTUBE_COOKIES_FILE` (optional; Pfad zur `cookies.txt` auf dem Host)
- `OPEN_WEBUI_API_KEY` (Open WebUI JWT Bearer; für Tool-Indexer / Admin API falls Role=admin)
- `WEBUI_SECRET_KEY`
- `POSTGRES_PASSWORD` (falls für einen Service verwendet)

Wichtig (Namenskonvention):
- **`OPEN_WEBUI_API_KEY` ist der primäre Name** für den Open WebUI JWT (Bearer Token) in `/etc/ai_stack/secrets.env`.
- `OWUI_API_KEY` ist nur ein **deprecated Alias** (ältere Doku/Configs). Falls du ihn noch irgendwo hast: auf `OPEN_WEBUI_API_KEY` umstellen.

Optionales Secret-Artefakt (Datei, nicht als Text-Value im Repo):
- `/etc/ai_stack/youtube_cookies.txt` (nur falls nötig, z. B. bei 429/Block auf YouTube)

### 3.2 Stack-spezifische Secretfiles (Least Privilege)

Diese Files sind **optional**. Du brauchst sie nur, wenn du Secrets physisch auf mehrere Dateien aufteilen willst.

Empfohlenes Default-Setup (SSOT bleibt 1 File):
- Compose wird mit **dem SSOT-File** gestartet: `docker compose --env-file /etc/ai_stack/secrets.env ...`
- **Least Privilege** wird durch die `environment:`-Sektionen in `docker-compose.yml` erreicht (nur Variablen, die dort explizit gesetzt sind, landen im Container).

Wenn du trotzdem trennen willst, kannst du zusätzlich „Minimal-Exports“ pflegen, z. B.:
- `/etc/ai_stack/open-webui.secrets.env`
- `/etc/ai_stack/mcp-transcript-miner.secrets.env`
- `/etc/ai_stack/traefik.secrets.env`

Hinweis: Diese Stack-Files sind dann **keine zweite SSOT**, sondern eine bewusste Aufteilung (oder automatisch generierte Exporte).

---

## 5) Docker Compose Start-Policy

### 5.1 Grundsatz

- Compose wird immer mit einem **expliziten** Env-File gestartet:
  - Default (SSOT): `docker compose --env-file /etc/ai_stack/secrets.env up -d`
  - Optional (Split): `docker compose --env-file /etc/ai_stack/<stack>.secrets.env up -d`

### 5.2 Keine impliziten .env im Repo

- Keine Nutzung von automatisch geladenen `.env` Dateien im Repo.
- Wenn ein Stack zwingend `.env` erwartet:
  - dann nur als Template ohne Werte (`.env.example`)
  - echte Werte außerhalb des Repo.

---

## 6) Optional: Docker “secrets” Feature

- Kann verwendet werden, wenn ein Service Secrets als Datei lesen kann.
- Nicht als Ersatz für SSOT gedacht.

Policy:
- Wenn Docker Secrets genutzt werden:
  - pro Service scope-bar
  - Name klar dokumentieren
  - keine Provider-Keys doppelt in Env + Secretfile (ein Pattern wählen)

---

## 7) Rotation & Incident Policy

### 7.1 Rotation

Keys rotieren, wenn:
- ein Secret in Chat/Log/Screenshot sichtbar war
- ein Container kompromittiert wirkt
- ein Backup/Export unkontrolliert geteilt wurde

### 7.2 Incident Ablauf (kurz)

1. Betroffene Keys identifizieren.
2. Keys rotieren (Provider-Seite).
3. `/etc/ai_stack/*.secrets.env` aktualisieren.
4. Stacks neu starten.
5. Nachträgliche Log- und Repo-Prüfung.

---

## 8) Dokumentationspflicht

Für jeden Stack existiert eine kurze `SECRETS.md` im Repo (ohne Werte), die dokumentiert:
- Welche Variablen benötigt werden
- Ob sie als Env (Container) oder außerhalb (Client) verwaltet werden
- Wo sie herkommen (`/etc/ai_stack/<stack>.secrets.env`)

Beispiel (open-webui):
- `WEBUI_SECRET_KEY` — Container Env — `/etc/ai_stack/secrets.env`
- `OPEN_WEBUI_API_KEY` — Tool/Indexer Env — `/etc/ai_stack/secrets.env`

---

## 8.1 Required Keys by Stack (Repo-SSOT, ohne Werte)

### open-webui

- Required:
  - `WEBUI_SECRET_KEY`
- Optional (je nach Provider/Setup):
  - `OPENAI_API_KEY`

### mcp-transcript-miner

- Required (für Runs + Knowledge Indexing):
  - `YOUTUBE_API_KEY`
  - `OPENROUTER_API_KEY`
  - `OPEN_WEBUI_API_KEY`
  - `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON`
- Recommended:
  - `OPEN_WEBUI_BASE_URL` (Default im Container: `http://open-webui:8080`)
- Optional:
  - `YOUTUBE_COOKIES_FILE` (z. B. `/host_secrets/youtube_cookies.txt`)
  - `OPEN_WEBUI_KNOWLEDGE_ID` (Fallback-Default, falls Topic-Mapping fehlt)

### mcp-context6 (context6 PoC)

- Optional (nur wenn `sync.start` mit `knowledge_id` genutzt wird):
  - `OPEN_WEBUI_API_KEY` (oder `OWUI_API_KEY` deprecated) — Admin Bearer Token
  - `OPEN_WEBUI_BASE_URL` (Default im Container: `http://open-webui:8080`)
  - `OPEN_WEBUI_PROCESS_POLL_INTERVAL_SECONDS`
  - `OPEN_WEBUI_PROCESS_TIMEOUT_SECONDS`

---

## 9) Offene Entscheidungen (zu tracken)

- Nutzen wir systemd, um Compose Stacks beim Boot zu starten?
  - Wenn ja: systemd Unit referenziert `EnvironmentFile=/etc/ai_stack/<stack>.secrets.env`.
- Welche Services brauchen wirklich shared Secrets?
  - Ziel: möglichst wenig Sharing.
