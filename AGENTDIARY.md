# Agent Diary

This diary tracks tasks, issues/bugs encountered, and how they were resolved.

## 2026-01-29
- Task: Add mandatory agent diary requirement and commit rules.
- Issues/Bugs: No agent diary existed and no explicit agent-level policy about diary + commit steps.
- Resolution: Moved mandatory diary + commit rules into `AGENTS.md`, removed `AGENT.md`, and updated docs references.
- Task: Fix missing `investing` Knowledge Collection by refreshing the Open WebUI Knowledge ID mapping.
- Issues/Bugs: `sync/topic/investing` targeted a stale Knowledge ID and failed to add files (HTTP 400 not found).
- Resolution: Created the `investing` collection in Open WebUI, updated `config/knowledge_ids.json`, and restarted the tm container to reload the mapping.
- Task: Make Knowledge-ID mapping resilient and re-run `investing` sync.
- Issues/Bugs: Stale Knowledge-ID mapping can break sync even when the collection exists by name.
- Resolution: Added a mapped-ID existence check with fallback to name lookup, rebuilt/restarted `tm`, and re-ran `sync/topic/investing` (success).
- Task: Disable Knowledge-ID mapping and verify sync + Knowledge files for `investing`.
- Issues/Bugs: Mapping can become stale and override name-based resolution.
- Resolution: Cleared `OPEN_WEBUI_KNOWLEDGE_ID_BY_TOPIC_JSON_PATH`, restarted `tm`, re-ran `sync/topic/investing` (success), and verified Knowledge files via OWUI API.
- Task: Future-proof Knowledge mapping state.
- Issues/Bugs: Stale local mapping files can reintroduce ID drift if mapping is re-enabled later.
- Resolution: Removed local `config/knowledge_ids.json` to avoid accidental stale mappings; rely on name-based resolution unless mapping is explicitly reintroduced.
- Task: Start a new Transcript Miner run for `investing`.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (auto-sync enabled).
- Task: Enable immediate per-video sync to Open WebUI after summary completion.
- Issues/Bugs: Auto-sync only ran after the full run finished.
- Resolution: Added per-summary sync hook in the TranscriptMiner LLM runner, passed new env flags via tm compose, and enabled `OPEN_WEBUI_SYNC_ON_SUMMARY` in config.
- Task: Start a new `investing` run to validate per-summary sync.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (run_id=e25029b7c98d401089ab4dc3f21912d8).
- Task: Ensure per-summary sync also triggers for existing summaries and streaming workers.
- Issues/Bugs: No per-summary sync logs; streaming path and “summary exists” short-circuit bypassed sync.
- Resolution: Added sync for valid-existing summaries and streaming LLM summary writes.
- Task: Restart tm to load per-summary sync changes and start a new investing run.
- Issues/Bugs: Previous run used old code without streaming/skip sync hooks.
- Resolution: Restarted `tm` and started `config_investing.yaml` (run_id=e66ad93907e24e338ffbea492cd120f7).
- Task: Fix crash in per-summary sync for existing summaries.
- Issues/Bugs: Run crashed with `UnboundLocalError` (fallback_title not initialized when summary already exists).
- Resolution: Initialized default metadata before early return and re-enabled per-summary sync path.
- Task: Start a new `investing` run after the per-summary sync fix.
- Issues/Bugs: None (manual trigger).
- Resolution: Triggered `POST /runs/start` with `config_investing.yaml` (run_id=9967297b4959455fb07b9536a8caed7d).
- Task: Check run completion status and auto-sync progress for investing.
- Issues/Bugs: Auto-sync still running; manual sync attempt timed out.
- Resolution: Verified run finished (exit_code=0) and auto-sync started; will retry sync status later.
- Task: Check final run status + auto-sync outcome and document OWUI UI timestamp caveat.
- Issues/Bugs: Auto-sync failed due to OWUI duplicate-content rejection; UI “Updated” timestamp does not reflect file adds.
- Resolution: Captured auto-sync error details and documented UI timestamp caveat in smoke-test runbook.
- Task: Create prompt engineering handover report for META summary quality.
- Issues/Bugs: Per-video summary considered too short given transcript richness.
- Resolution: Assembled transcript, summary, and prompt into `enhance_prompt_engineering.md` with gap analysis and recommendations.
- Task: Capture expert prompt-engineering tips and switch workflow to investing_test for alpha.
- Issues/Bugs: Current summaries feel thin; repeated full investing runs are too heavy for alpha iteration.
- Resolution: Added expert tips to `docs/prompt_engineering_expert_notes.md` and documented investing_test focus in `TODO.md`.

## 2026-01-30
- Task: Document the investing_test alpha workflow and close the corresponding TODO.
- Issues/Bugs: Root README lacked a clear, repo-wide workflow for prompt-iteration runs.
- Resolution: Added an Investing-Test Workflow section to `README.md`, marked the TODO complete, and updated `CHANGELOG.md`.
- Task: Move the agent diary to the repo root.
- Issues/Bugs: Agent diary path needed to align with the new location and naming.
- Resolution: Copied the diary to `AGENTDIARY.md`, removed `docs/agent_diary.md`, and updated docs references.
- Task: Locate and clean up a possible typo file `AGENETDIARY.md`.
- Issues/Bugs: File not found in repo root or subdirectories.
- Resolution: Searched the workspace; no file to delete.
- Task: Create a Schema v3 prompt-engineering handover report (Meta summary).
- Issues/Bugs: Current summaries are rendered without quotes/evidence, making them hard to audit.
- Resolution: Added `enhance_prompt_engineering_v3.md` with a v3 direction (numbers completeness, verbatim vs normalized values, evidence/persistence improvements).

## 2026-01-31
- Aufgabe: Offene Punkte/Optionen zu Open WebUI Knowledge Auto-Create + Duplikate in TODO dokumentiert.
- Probleme/Bugs/Issues: Unklarheit zu unerwuenschten Knowledge-Collections (bitcoin/crypto) durch Auto-Create bei RAG-Anfragen.
- Loesung: TODO-Items mit Optionen (Request-Flag, Allowlist, Kombination) + Cleanup/Sync-Plan erfasst.

## 2026-01-31
- Aufgabe: TODO um Markdown-Linter-Wunsch ergänzt (Repo-wide, CI-Option).
- Probleme/Bugs/Issues: Keine.
- Loesung: Neuer TODO-Eintrag mit Optionen/Scope/CI-Hinweis.

## 2026-01-31
- Aufgabe: TODO um Watchdog/OWUI-Stop-Klaerung und Aktionen ergaenzt.
- Probleme/Bugs/Issues: OWUI wurde manuell gestoppt; wahrscheinlich Temp-Stop durch Watchdog (Default-Target owui).
- Loesung: TODO fuer Log-Check (watchdog.alert.jsonl) + Anpassung der Temp-Stop-Regeln erfasst.

## 2026-01-31
- Aufgabe: TODO um Lessons-Learned + Doku-Pfade fuer Watchdog/OWUI-Temp-Stop erweitert.
- Probleme/Bugs/Issues: Kontext-Reset erfordert persistente Doku; Watchdog Temp-Stop war Ursache fuer OWUI-Ausfall.
- Loesung: TODO-Erweiterung mit klaren Doku-Optionen (plan/README/CHANGELOG/Runbook).

## 2026-01-31
- Aufgabe: Anfrage zur CPU-Temperatur-Auslese geprüft (Repo-first).
- Probleme/Bugs/Issues: Keine.
- Loesung: Vorhandene Watchdog-Implementierung (sysfs/thermal/hwmon) und Doku als Referenz fuer Host-Temperatur-Auslese herangezogen.

## 2026-01-31
- Aufgabe: Aktuelle CPU-Temperatur auf dem Host ausgelesen.
- Probleme/Bugs/Issues: Python/Python3 nicht installiert; Locale nutzte Komma als Dezimaltrennzeichen.
- Loesung: Messung per sysfs + awk (LC_ALL=C) ausgefuehrt und Max/Min ermittelt.

## 2026-01-31
- Aufgabe: Frage nach Zeitraum fuer Max/Min-Temperaturen geklaert.
- Probleme/Bugs/Issues: Missverstaendnis, ob Max/Min historische Werte sind.
- Loesung: Erklaert, dass sysfs-Reads Momentaufnahmen sind; Hinweis auf Watchdog-Logs fuer Verlauf.

## 2026-01-31
- Aufgabe: Nachfrage zum Zeitrahmen fuer Temperaturwerte beantwortet.
- Probleme/Bugs/Issues: Wiederholtes Missverstaendnis zwischen Zeitrahmen und Sensor-Set.
- Loesung: Klarstellung, dass die Werte eine Momentaufnahme sind (kein Zeitrahmen).

## 2026-01-31
- Aufgabe: Offene Tasks aus TODO beantwortet.
- Probleme/Bugs/Issues: Keine.
- Loesung: TODO-Status aus `TODO.md` gelesen und offene Punkte zusammengefasst.

## 2026-01-31
- Aufgabe: Watchdog OWUI-Stop geklaert und Defaults geschaerft.
- Probleme/Bugs/Issues: OWUI wurde wegen Temp-Stop bei 60C/2 Messungen gestoppt.
- Loesung: Alert-Log verifiziert (2026-01-31T00:29:43Z, 63C) und Defaults in `watchdog/.config.env.example` auf 95C/3 Messungen angehoben; Doku aktualisiert.

## 2026-01-31
- Aufgabe: Watchdog/OWUI Stop Lessons Learned dokumentiert.
- Probleme/Bugs/Issues: Kontext-Reset kann Wissen ueber Temp-Stop-Trigger verlieren.
- Loesung: Log-Pfad/Trigger in `docs/plan_watchdog_monitoring.md` festgehalten und TODO abgeschlossen.

## 2026-01-31
- Aufgabe: Knowledge Auto-Create Governance umgesetzt.
- Probleme/Bugs/Issues: Auto-Create konnte unbeabsichtigt Collections anlegen.
- Loesung: Auto-Create nur mit Request-Flag + optionaler Allowlist; Doku/Config aktualisiert.

## 2026-01-31
- Aufgabe: Re-Sync nach Summary-Rebuild fuer investing abgeschlossen.
- Probleme/Bugs/Issues: Open WebUI meldete Duplicate-Content und brach den Sync ab.
- Loesung: Duplicate-Content beim Knowledge-Add als `skipped` behandelt; tm neu gebaut; `sync/topic/investing` erfolgreich (109/109).

## 2026-01-31
- Aufgabe: OWUI Duplicate-Anzeige geprueft (Investing Knowledge).
- Probleme/Bugs/Issues: UI zeigte viele Duplikate; API zeigte nur 30 Files ohne Duplikate.
- Loesung: Duplikat-Check via OWUI API (keine doppelten Dateinamen); OWUI-Container neu gestartet.

## 2026-01-31
- Aufgabe: OWUI Duplicate-Anzeige erneut geprueft (Investing Knowledge).
- Probleme/Bugs/Issues: UI zeigte viele Duplikate trotz Restart.
- Loesung: Vollstaendigen API-Export mit Pagination ausgewertet: 587 Files, Duplikate vorhanden (109 Filename-Duplikate, 92 Hash-Duplikate).

## 2026-01-31
- Aufgabe: OWUI Investing Knowledge dedupliziert (Hash + Dateiname).
- Probleme/Bugs/Issues: Delete-API meldete teils 400 (File bereits entfernt).
- Loesung: Entfernen wiederholt bis keine Duplikate mehr vorhanden; Bestand jetzt 109 Files, keine Hash/Name-Duplikate.

## 2026-01-31
- Aufgabe: Praeventiven OWUI-Dedup-Precheck implementiert.
- Probleme/Bugs/Issues: Wiederholte Uploads konnten vor Dedup entstehen.
- Loesung: Pre-Check gegen OWUI (Hash/Dateiname) vor Upload + Cache-TTL (configurierbar).

## 2026-01-31
- Aufgabe: TM neu gebaut/neu gestartet, um Dedup-Precheck zu aktivieren.
- Probleme/Bugs/Issues: Keine.
- Loesung: `docker compose ... up -d --build` fuer tm ausgefuehrt.

## 2026-01-31
- Aufgabe: Debug-Proxy Architektur auf Root-Ordner umgestellt.
- Probleme/Bugs/Issues: Vorab-Entwurf lag unter `open-webui/`; Name/Scope unklar.
- Loesung: Debug-Proxy als eigenes Service-Root (`debug-proxy/`) mit JSONL-Logging; OWUI-Config angepasst.

## 2026-01-31
- Aufgabe: Debug-Proxy Log als Ringbuffer (nur letzte 100k Zeichen).
- Probleme/Bugs/Issues: Per-request truncation war unerwünscht.
- Loesung: Per-request truncation deaktiviert; globales Zeichenlimit beibehalten.

## 2026-01-31
- Aufgabe: debug-proxy und owui neu gestartet fuer Test.
- Probleme/Bugs/Issues: debug-proxy .config.env fehlte.
- Loesung: `.config.env` aus Example erzeugt, debug-proxy und owui neu gestartet.

## 2026-01-31
- Aufgabe: OWUI Proxy-Env gesetzt und neu gestartet.
- Probleme/Bugs/Issues: Keine.
- Loesung: `open-webui/.config.env` um Debug-Proxy Variablen ergaenzt, OWUI neu gestartet und Env verifiziert.

## 2026-01-31
- Aufgabe: Debug-Proxy CA-Trust Fix.
- Probleme/Bugs/Issues: OWUI TLS-Verify schlug fehl (mitmproxy nutzte anderes confdir).
- Loesung: debug-proxy auf `confdir=/data/mitmproxy` fixiert, Doku aktualisiert.

## 2026-01-31
- Aufgabe: Debug-Proxy Logs lesbar machen.
- Probleme/Bugs/Issues: Responses waren gzip-komprimiert.
- Loesung: Gzip-Responses werden vor Logging entpackt.

## 2026-01-31
- Aufgabe: Ringbuffer stabilisiert.
- Probleme/Bugs/Issues: UTF-8 Decode-Error beim Trunkieren der Log-Datei.
- Loesung: Ringbuffer auf byte-basiertes Truncation umgestellt.

## 2026-01-31
- Aufgabe: Debug-Proxy Logs und flows.jsonl geprueft.
- Probleme/Bugs/Issues: In Logs ist ein alter UTF-8 Decode-Error sichtbar (vor Fix).
- Loesung: Aktuelle Logs zeigen OpenRouter-Calls; flows.jsonl enthaelt lesbare JSON-Responses.

## 2026-01-31
- Aufgabe: Letzte 2 Proxy-Flows extrahiert.
- Probleme/Bugs/Issues: Host hat kein python; JSONL musste via jq geparst werden.
- Loesung: Letzte 2 JSON-Objekte via jq extrahiert und nach `/home/wasti/ai_stack_data/debug-proxy/last_flows.json` geschrieben.

## 2026-01-31
- Aufgabe: Python-Installation versucht.
- Probleme/Bugs/Issues: Keine Rechte auf APT-Lock (`/var/lib/apt/lists/lock`).
- Loesung: Abbruch; benoetigt sudo/root fuer `apt-get`.

## 2026-01-31
- Aufgabe: Python-Installation verifiziert.
- Probleme/Bugs/Issues: Keine.
- Loesung: `python3 --version` geprüft (Python 3.13.5).

## 2026-01-31
- Aufgabe: Proxy-Flows per Python ausgewertet (letzte Requests + System/User/Response Preview).
- Probleme/Bugs/Issues: Ringbuffer kann mitten in JSON schneiden; nur valide JSON-Zeilen auswertbar.
- Loesung: Robust-Parser (invalid lines skip) und Ausgabe der letzten validen Flows inkl. System-Hash.

## 2026-01-31
- Aufgabe: Debug-Proxy Ringbuffer an JSONL-Zeilengrenzen ausgerichtet.
- Probleme/Bugs/Issues: Byte-Truncation konnte JSONL-Zeilen zerschneiden und Parsing erschweren.
- Loesung: Beim Trunkieren wird die erste unvollstaendige Zeile verworfen; Default-Limit auf 150k erhoeht.

## 2026-01-31
- Aufgabe: TODO fuer Apache Tika Docker-Installation ergaenzt.
- Probleme/Bugs/Issues: Keine.
- Loesung: TODO-Item in `TODO.md` erfasst; CHANGELOG aktualisiert.

## 2026-01-31
- Aufgabe: Debug-Proxy Log-Datei im Repo leichter auffindbar gemacht.
- Probleme/Bugs/Issues: flows.jsonl liegt unter `/home/wasti/ai_stack_data` und ist im Repo nicht sichtbar.
- Loesung: Lokalen Symlink `debug-proxy/flows.jsonl` angelegt und per `.gitignore` vom Commit ausgeschlossen; README-Hinweis ergaenzt.

## 2026-01-31
- Aufgabe: Debug-Proxy last_flows.json im Repo-Tree verlinkt.
- Probleme/Bugs/Issues: Extrahierte Datei lag nur unter `/home/wasti/ai_stack_data` und war im Service-Ordner nicht sichtbar.
- Loesung: Lokalen Symlink `debug-proxy/last_flows.json` angelegt und in `.gitignore` ausgeschlossen; README ergaenzt.

## 2026-01-31
- Aufgabe: Codex Skill fuer OWUI Prompt-Debug/PDCA erstellt.
- Probleme/Bugs/Issues: Prompt-Settings liegen in OWUI `webui.db` (Container) und Debugging war nicht reproduzierbar dokumentiert.
- Loesung: Skill `skills/owui-prompt-debug-loop/` angelegt inkl. Scripts zum Extrahieren/Reporten von `debug-proxy/flows.jsonl` und zum sicheren Dump/Patch von Model-/Folder-Prompts + RAG-Template (mit DB-Backup).

## 2026-01-31
- Aufgabe: Apache Tika fuer Open WebUI als Compose-Service integriert.
- Probleme/Bugs/Issues: OWUI lief (optional) hinter debug-proxy; interner Tika-Call darf nicht ueber Proxy laufen.
- Loesung: `tika` Service in `open-webui/docker-compose.yml` hinzugefuegt und `OWUI_NO_PROXY` um `tika` erweitert.

## 2026-01-31
- Aufgabe: OWUI Prompt-Debug-Loop vorbereitet (Investing) und Patch-Skripte repariert.
- Probleme/Bugs/Issues: Bash-HereDoc nutzte ungueltige Substitutionen ("${...!r}") und brach bei owui_dump/patch ab.
- Loesung: Scripts auf Env-Variablen umgestellt und Referenz-Prompts fuer Model/Folder/RAG befuellt; Prompt-Update in der OWUI DB angewendet.

## 2026-01-31
- Aufgabe: Prompt-Test via Open WebUI API (Investing-Chat) ausgefuehrt und Debug-Proxy-Flow erzeugt.
- Probleme/Bugs/Issues: Erster API-Call lief in Timeout.
- Loesung: Request mit laengerem Timeout wiederholt; Flow erfolgreich abgeschlossen.

## 2026-01-31
- Aufgabe: Neues Skill fuer OWUI Prompt-Tests via API erstellt (inkl. Flow-Report) und Regel zur stetigen Verbesserung ergaenzt.
- Probleme/Bugs/Issues: init_skill.py war nur als python3 verfuegbar.
- Loesung: Skill mit python3 initialisiert; Scripts + Referenzprompt hinzugefuegt; AGENTS/README/CHANGELOG aktualisiert.

## 2026-01-31
- Aufgabe: RAG Top-K Aenderung (100 -> 30) dokumentiert.
- Probleme/Bugs/Issues: Keine.
- Loesung: README/CHANGELOG aktualisiert und aktuellen Setting-Stand erfasst.

## 2026-01-31
- Aufgabe: OpenClaw Install/Telegram Quellen notiert.
- Probleme/Bugs/Issues: Keine.
- Loesung: Notizdatei in docs/ angelegt und Doku-Index + Changelog aktualisiert.

## 2026-01-31
- Aufgabe: Open WebUI API-Key-Status lokal geprueft (0.7.2).
- Probleme/Bugs/Issues: API-Key Erstellung liefert 403 trotz ENABLE_API_KEYS=true.
- Loesung: Ursache als fehlende Permission identifiziert (features.api_keys default false); Admin wird nicht gebypasst.

## 2026-01-31
- Aufgabe: API-Key-Erstellung in OWUI 0.7.2 aktiviert (Default User Permissions).
- Probleme/Bugs/Issues: API-Key Creation lieferte 403 trotz ENABLE_API_KEYS=true.
- Loesung: Default User Permissions via Admin API gesetzt (features.api_keys=true); API-Key Creation funktioniert danach.

## 2026-01-31
- Aufgabe: OWUI User "openclaw" angelegt und als role=user gesetzt.
- Probleme/Bugs/Issues: Signup scheiterte mit ungueltigem Email-Format (openclaw@local).
- Loesung: Email auf openclaw@example.com gesetzt, Signup via Admin-Config (ENABLE_SIGNUP temporaer true) durchgefuehrt, danach wieder deaktiviert; Email in open-webui/openclaw_user.txt dokumentiert.

## 2026-01-31
- Aufgabe: OWUI User-Name fuer openclaw auf wasticlaw-1 gesetzt.
- Probleme/Bugs/Issues: Keine.
- Loesung: User per Admin API aktualisiert und Record-Datei angepasst.

## 2026-01-31
- Aufgabe: Passwort fuer wasticlaw-1 gesetzt und in .env hinterlegt (secrets-only).
- Probleme/Bugs/Issues: Keine.
- Loesung: User-Passwort via Admin API aktualisiert und OPEN_WEBUI_OPENCLAW_PASSWORD gesetzt.

## 2026-01-31
- Aufgabe: OWUI openclaw user email auf wasticlaw-1@example.com umgestellt.
- Probleme/Bugs/Issues: Keine.
- Loesung: User per Admin API aktualisiert und Record-Datei angepasst.

## 2026-01-31
- Aufgabe: OpenClaw Service-Ordner scaffolded (Compose + Config + README) und Doku-Index aktualisiert.
- Probleme/Bugs/Issues: Keine.
- Loesung: openclaw/ mit docker-compose.yml, .config.env.example, README; README/Docs/Changelog aktualisiert.

## 2026-01-31
- Aufgabe: OpenClaw Upstream-Repo geklont und docker-setup.sh ausgefuehrt.
- Probleme/Bugs/Issues: Gateway-Token wurde im Setup-Output ausgegeben (secrets exposure in terminal output).
- Loesung: Token in repo .env uebernommen; Hinweis zur Rotation gegeben.

## 2026-01-31
- Aufgabe: OpenClaw Gateway Status geprueft.
- Probleme/Bugs/Issues: Gateway restartet mit "Missing config".
- Loesung: Setup erforderlich (openclaw setup); Hinweis fuer naechsten Schritt.

## 2026-01-31
- Aufgabe: OpenClaw Gateway konfiguriert und lokal gestartet (127.0.0.1:18789).
- Probleme/Bugs/Issues: openclaw setup scheiterte wegen Berechtigungen; Gateway restartete wegen missing config.
- Loesung: setup mit --user 1001:1001 ausgefuehrt, openclaw.json lesbar gemacht, Gateway mit repo-compose (localhost bind) gestartet.

## 2026-01-31
- Aufgabe: OWUI via Tailscale Serve unter /owui stabil gemacht.
- Probleme/Bugs/Issues: "Backend Required" durch fehlende Asset/API-Weiterleitung bei Pfad-Serve; _app Bundles 404.
- Loesung: Tailscale Serve Pfade fuer /owui, /_app, /static, /manifest.json, /api auf korrekte Upstream-Pfade gesetzt und Doku ergaenzt.

## 2026-02-01
- Aufgabe: OWUI und OpenClaw Erreichbarkeit wiederhergestellt.
- Probleme/Bugs/Issues: OWUI Container gestoppt; OpenClaw Pfad fehlte in Tailscale Serve.
- Loesung: OWUI Container gestartet; Tailscale Serve /openclaw auf 127.0.0.1:18789 gesetzt und Operator-Rechte dokumentiert.

## 2026-02-01
- Aufgabe: Dokumentation zu OWUI Root-Serve und OpenClaw Pfad-Konflikt aktualisiert.
- Probleme/Bugs/Issues: OWUI redirectet auf `/`; OpenClaw nutzt absolute `/api` und kollidiert mit OWUI bei Pfad-Serve.
- Loesung: OWUI Root-Serve als stabiler Zugriff dokumentiert; OpenClaw eigener Host/Port empfohlen.

## 2026-02-01
- Aufgabe: Access-Notiz (Tailscale vs LAN) fuer OWUI/OpenClaw erstellt.
- Probleme/Bugs/Issues: /owui Login redirectet auf `/` (404 wenn Root nicht gemappt); /openclaw kollidiert wegen absolutem `/api` mit OWUI.
- Loesung: Notiz unter docs/ abgelegt und in docs/README.md verlinkt.

## 2026-02-01
- Aufgabe: Doku erweitert: Hostname-Split fuer OWUI/OpenClaw (2 Tailscale Nodes auf einem Host).
- Probleme/Bugs/Issues: Pfad-Serve kollidiert (OWUI redirect zu `/`, OpenClaw absolute `/api`/`/ws`).
- Loesung: Konkrete Schritte dokumentiert (Host umbenennen + zweiter tailscaled Docker-Node fuer OpenClaw).

## 2026-02-01
- Aufgabe: Hostname-Split Anleitung korrigiert (Docker tailscaled ohne host-network).
- Probleme/Bugs/Issues: Zweiter tailscaled im `--network=host` kollidiert (TUN `tailscale0` busy / Port-Konflikte).
- Loesung: Zweiten Node im eigenen NetNS laufen lassen und OpenClaw ueber Docker-Netz `ai-stack` via `openclaw-gateway:18789` proxien.

## 2026-02-01
- Aufgabe: Transcript-Miner Investing Channel-Liste erweitert.
- Probleme/Bugs/Issues: Keine.
- Loesung: YouTube Channel `@BrunoKreidler` in `transcript-miner/config/config_investing.yaml` hinzugefuegt.

## 2026-02-01
- Aufgabe: Repo-Housekeeping: Codex lokale Metadata aus Git fernhalten.
- Probleme/Bugs/Issues: Untracked Ordner `.codex/` tauchte im Repo auf.
- Loesung: `.codex/` in `.gitignore` aufgenommen.

## 2026-02-02
- Aufgabe: OpenClaw Gateway von Container auf native Host-Ausfuehrung umgestellt, Hostname-Setup beibehalten.
- Probleme/Bugs/Issues: Tailscale-Proxy im `tailscaled-openclaw` Container kann localhost nicht erreichen.
- Loesung: Native Gateway auf loopback:18789, TCP-Bridge via `socat` an Docker-Gateway-IP:18790, Tailscale Serve auf Bridge umgestellt.

## 2026-02-02
- Aufgabe: Codex/VSC Remote-SSH Auth gegen Tailscale-DNS Ausfaelle gehaertet (dauerhaft, ohne sudo-Abhaengigkeit).
- Probleme/Bugs/Issues: Erste Version der Cron-Installer-Blockentfernung hatte fehlerhafte `sed` Syntax.
- Loesung: Guard-Skripte fuer Check/Remediation/Cron-Install erstellt, Blockentfernung auf robustes `awk` umgestellt, Cron aktiv installiert und End-to-End verifiziert (forced failure + auto-fix).

## 2026-02-02
- Aufgabe: TODO um gewuenschten Transcript-Miner Ausbau fuer Influencer-Trackrecord erweitert.
- Probleme/Bugs/Issues: Keine technischen Blocker; Anforderungen mussten in umsetzbare Teilziele (Signal-Extraktion, Kurs-Freeze, Langzeitbewertung) strukturiert werden.
- Loesung: Neues TODO-Backlog-Item mit klaren Datenpunkten, DoD-Entwurf und Auswertungsziel dokumentiert; CHANGELOG entsprechend aktualisiert.

## 2026-02-03
- Aufgabe: Ursache geprueft, warum OWUI bei investing zuletzt "12 hours ago" fuer Summary-Files zeigte.
- Probleme/Bugs/Issues: `tm`-Runs (z. B. 2026-02-02 20:00 UTC und 23:00 UTC) liefen, hatten aber DNS-Fehler (`Unable to find the server at youtube.googleapis.com`) und konnten keine frischen Transkripte laden.
- Loesung: Root Cause bestaetigt: Container-DNS zeigte auf stale Docker-Upstream `100.100.100.100` (geerbt aus alter Host-Resolver-Lage); `tm` neu gestartet, DNS im Container auf `192.168.0.1` aktualisiert, manuellen Investing-Run gestartet (`df96c841...`) und neue Summaries erzeugt (11 neue Files in den letzten ~25 Minuten).

## 2026-02-03
- Aufgabe: OpenClaw-Doku von Docker-first auf host-native Betrieb umgestellt und stale Docker-Reste bereinigt.
- Probleme/Bugs/Issues: Repo-Doku war noch Docker-zentriert und hat dadurch zu falschen CLI-Empfehlungen gefuehrt.
- Loesung: `openclaw/README.md`, `README.md` und `docs/README.md` auf host-native Standard aktualisiert; stale Container `openclaw-gateway` entfernt; Healthcheck mit `openclaw gateway status` bestaetigt.

## 2026-02-03
- Aufgabe: Finalen OpenClaw-Cleanup abgeschlossen, um Docker-Reste zu entfernen und Betrieb eindeutig host-native zu halten.
- Probleme/Bugs/Issues: Veraltete OpenClaw-Docker-Images (`openclaw*`) waren noch lokal vorhanden und konnten zu Missverstaendnissen fuehren.
- Loesung: `openclaw/docker-compose.yml` + `.config.env.example` klar als deprecated Fallback markiert, alte OpenClaw-Images entfernt, Laufzeit geprueft (`openclaw gateway status` weiterhin OK).

## 2026-02-03
- Aufgabe: OpenClaw final so bereinigt, dass kein Repo-Betriebspfad mehr ueber Docker laeuft.
- Probleme/Bugs/Issues: Vorherige Bereinigung liess noch Docker-Fallback-Dateien und Legacy-Formulierungen im Repo.
- Loesung: `openclaw/docker-compose.yml` und `openclaw/.config.env.example` entfernt, `openclaw/README.md` auf rein host-native Betrieb gestrafft, Root-README bereinigt und lokale OpenClaw-Upstream-Kopie geloescht.

## 2026-02-03
- Aufgabe: OpenClaw Reconfigure-Ergebnis mit finalen Pfaden dauerhaft dokumentiert.
- Probleme/Bugs/Issues: Workspace-Pfad war zuvor auf Docker-Home (`/home/node/...`) und fuehrte zu EACCES.
- Loesung: Host-native Pfade festgehalten (`~/.openclaw/openclaw.json`, `~/.openclaw/workspace`, `~/.openclaw/agents/main/sessions`) und in `openclaw/README.md` verankert.

## 2026-02-03
- Aufgabe: Offenen OpenClaw-Telegram Blocker fuer naechste Session explizit in TODO verankert.
- Probleme/Bugs/Issues: Trotz laufendem Telegram-Channel trat weiterhin `disconnected (1008): pairing required` auf; Session musste unterbrochen werden.
- Loesung: TODO-Eintrag mit aktuellem Status, bereits gesetzten Configs und konkretem naechsten Ablauf (pairing list/approve, Live-Logs, BotFather Privacy) ergaenzt; CHANGELOG aktualisiert.

## 2026-02-03
- Aufgabe: Ursache fuer ausgebliebenen OWUI-Sync bei Transcript Miner analysiert und stabilisiert.
- Probleme/Bugs/Issues: Auto-Sync lief als `partial/failed`, obwohl der Run selbst erfolgreich war; Open WebUI File-Processing schlug zeitweise fehl.
- Loesung: Root Cause auf transienten Proxy/DNS-Fehler eingegrenzt (`debug-proxy` konnte `openrouter.ai` zeitweise nicht aufloesen -> OWUI `process/status=failed`); fehlende Eintraege manuell per `sync/topic/investing` nachgesynct (142/142 indexed, 0 errors); Retry-Logik fuer `POST /index/transcript` (Upload/Process/Add mit Backoff) implementiert und Doku/Config aktualisiert.

## 2026-02-03
- Aufgabe: Prompt-Engineering Testumgebung mit den 10 neuesten Transcript/Summary-Paaren aufgebaut.
- Probleme/Bugs/Issues: Lokale Python-Umgebung war teilweise inkonsistent (gebrochener venv-Python Symlink), initiales Generator-Skript lief dadurch nicht.
- Loesung: Fixture als robustes Bash-Skript umgesetzt (`transcript-miner/tests/prompt-engineering/_build_prompt_engineering_fixture.sh`), OpenRouter direkt per `curl` aufgerufen und je Video drei Vergleichsdateien erzeugt (`_transcript`, `_sumold`, `_sumnew`) plus `_promptold.md`/`_promptnew.md` und `_manifest.json`.

## 2026-02-03
- Aufgabe: Ziele fuer das Prompt-Engineering/RAG-Tuning als kurze, explizite Notiz abgelegt.
- Probleme/Bugs/Issues: Keine.
- Loesung: `_goals.md` in `transcript-miner/tests/prompt-engineering/` hinzugefuegt und Living Docs an den neuen Fixture-Inhalt angepasst.

## 2026-02-03
- Aufgabe: Prompt-Engineering Ziele um Recency-Weighting und Long-term Company-Dossiers erweitert.
- Probleme/Bugs/Issues: Prompt-/RAG-Problem: aeltere Summaries koennen bei Crypto/News-Topics obsolet sein und sollten weniger Gewicht bekommen; Fundamentals sollen separat langfristig gepflegt werden.
- Loesung: In `_goals.md` konkrete Strategien dokumentiert (Zeit-Decay/Recency-Buckets, separate Collections recent/archive, Answer-Policy) sowie Ansatz fuer separaten Dossier-Agent mit eigener OWUI Knowledge-Collection (`company_dossiers`).

## 2026-02-03
- Aufgabe: OWUI/RAG Ist-Setup im Prompt-Engineering Ziel-Dokument festgehalten.
- Probleme/Bugs/Issues: Fuer Entscheidungen wie \"Zeit-Decay Reranking\" muss klar sein, ob unser aktueller Stack ueberhaupt ein Reranking-Backend nutzt/unterstuetzt.
- Loesung: `_goals.md` um konkrete Setup-Details erweitert (OWUI in Docker, Persistenz `owui-data`, `webui.db` + `vector_db`, aktuelles Embedding-Modell `baai/bge-m3`, `top_k=30`, Reranker derzeit nicht konfiguriert).

## 2026-02-03
- Aufgabe: OWUI-Stack-Grenzen/ Hebel (Topic-Isolation, Recency-Routing, Reranker-Realitaet, Chunking) in `_goals.md` konkretisiert.
- Probleme/Bugs/Issues: Ohne explizit aktives Reranking bzw. ohne eigenen Ranker ist echtes Time-Decay-Scoring nicht \"einfach so\" moeglich.
- Loesung: `_goals.md` um eine Setup-spezifische Einordnung erweitert (was sofort wirkt vs. was Zusatzarbeit braucht).

## 2026-02-03
- Aufgabe: TODO fuer naechste Session vorbereitet (Prompt-Engineering + RAG Umsetzung).
- Probleme/Bugs/Issues: OWUI Remote-Zugriff via Tailscale liefert beim Chatten teils HTTP 500; ausserdem muss der neue topic-isolated Prompt in den Indexing-Flow integriert werden.
- Loesung: `TODO.md` um einen konkreten Plan fuer 2026-02-04 erweitert inkl. OWUI RAG Settings Snapshot (Embedder/Top-K/Chunking/Reranker-Status) und Integrationsaufgaben fuer `_promptnew.md` + `_goals.md`.

## 2026-02-03
- Aufgabe: TODO um konkrete OWUI RAG-Tuning-Empfehlungen aus der Chat-History erweitert.
- Probleme/Bugs/Issues: Vorher stand nur der Ist-Stand aus `webui.db` im TODO; die empfohlenen Zielwerte (Hybrid Search/Reranking/Top-K/Chunking) fehlten.
- Loesung: `TODO.md` um \"Empfehlung (aus Chat)\" erweitert: Hybrid Search an, Reranking Engine/Model setzen (z. B. `BAAI/bge-reranker-v2-m3`), `top_k` reduzieren (10–20), `top_k_reranker` 3–8 sowie Chunking (token-basiert, 350–650/500–1000 Tokens, Overlap 80–120) + Layout-Regeln.

## 2026-02-04
- Aufgabe: OWUI-Erreichbarkeit fuer `https://owui.tail027324.ts.net/` analysiert (warum Webpage nicht erreichbar).
- Probleme/Bugs/Issues: `owui` Container lief nicht; `tailscale serve` zeigte zwar korrektes Root-Proxy auf `127.0.0.1:3000`, aber lokal war Port 3000 nicht erreichbar (`connection refused`).
- Loesung: OWUI-Service mit Compose erneut gestartet (`docker compose ... -f open-webui/docker-compose.yml up -d owui`) und Laufzeit geprueft (`docker ps`, `curl http://127.0.0.1:3000` liefert wieder HTTP 200).

## 2026-02-04
- Aufgabe: Verifiziert, ob der neue Prompt (`tests/prompt-engineering/_promptnew.md`) bereits produktiv auf neue Transcripts angewandt wird, und Container-Status geprueft.
- Probleme/Bugs/Issues: Erwartung war moeglicherweise, dass `_promptnew.md` bereits live verwendet wird; tatsaechlich nutzt die Pipeline weiterhin `analysis.llm.system_prompt`/`user_prompt_template` aus `transcript-miner/config/config_investing.yaml` bzw. `config_investing_test.yaml`.
- Loesung: Laufende Summaries und aktuelle Configs gegengeprueft; aktuelle Summary-Struktur bestaetigt (`## Source`, `## Summary`, ...), keine `<<<DOC_START>>>` Wrapper aus `_promptnew.md`; Docker-Check zeigt keine `dead/exited` Container.

## 2026-02-04
- Aufgabe: Neuen Prompt (`transcript-miner/tests/prompt-engineering/_promptnew.md`) produktiv fuer zukuenftige Summaries aktiviert und auf die 20 zuletzt heruntergeladenen Transcripts angewandt.
- Probleme/Bugs/Issues: Prompt V2 nutzt Wrapper/Sections (`<<<DOC_START>>>`, `Executive Summary`, `Opportunities`), die nicht 1:1 zur bisherigen Normalisierung (`Summary`, `Key Points & Insights`, `Chances`) passten; ausserdem erwartet der neue User-Prompt mehr Metadaten-Placeholders.
- Loesung: `config_investing.yaml` und `config_investing_test.yaml` auf Prompt V2 umgestellt, `llm_runner.py` um zusaetzliche User-Prompt-Variablen erweitert und V2-Wrapper in der Normalisierung gemappt; danach 20 neueste Transcript-Dateien per `summarize_transcript_ref` neu generiert (20/20 erfolgreich).

## 2026-02-04
- Aufgabe: TODO um neuen Wunsch erweitert: MCP-Server fuer zuverlaessiges Embedding von SEC Filings.
- Probleme/Bugs/Issues: Wunsch war knapp formuliert; fuer Umsetzbarkeit mussten konkrete Muss-Kriterien und DoD in TODO ergaenzt werden.
- Loesung: Neues priorisiertes TODO-Item mit Zielbild, Robustheitskriterien (idempotente Upserts, Retry/Resume, Metadaten, Monitoring) und klarer Definition of Done eingetragen; CHANGELOG dazu aktualisiert.

## 2026-02-04
- Aufgabe: HTTP 502 auf `owui.tail027324.ts.net` analysiert und Open WebUI wieder online gebracht.
- Probleme/Bugs/Issues: `tailscale serve` war korrekt auf `http://127.0.0.1:3000` gemappt, aber der `owui` Container war gestoppt (`Exited (0)`), daher lieferte der Upstream nicht.
- Loesung: Open-WebUI-Service via Compose neu gestartet (`up -d owui`), Healthcheck bis `healthy` verifiziert und lokalen Endpoint mit `curl http://127.0.0.1:3000` auf HTTP 200 bestaetigt.

## 2026-02-04
- Aufgabe: Root-Cause fuer haeufig gestopptes OWUI + scheinbar wirkungslosen Summary-Prompt untersucht.
- Probleme/Bugs/Issues: `watchdog` stoppte `owui` mehrfach bei moderaten Temperaturen, weil `WATCHDOG_TEMP_STOP_*` im Compose nicht gesetzt waren und dadurch ungewollt Code-Defaults (`60C`, `2` Messungen) griffen; bei Prompt V2 wirkte Output "alt", weil Persistierung absichtlich auf kanonische Summary-Sections normalisiert.
- Loesung: `watchdog/docker-compose.yml` um `WATCHDOG_TEMP_STOP_THRESHOLD_C`, `WATCHDOG_TEMP_STOP_CONSEC`, `WATCHDOG_TEMP_STOP_CONTAINER_NAMES` ergaenzt (jetzt effektiv 95C/3/owui), Service neu erstellt; zudem README/TODO aktualisiert, um das Prompt-V2-Normalisierungsverhalten transparent zu machen.

## 2026-02-04
- Aufgabe: Watchdog auf User-Wunsch bis auf Weiteres gestoppt und Status dokumentiert; Prompt-Normalisierung in einfacher Sprache erklaert.
- Probleme/Bugs/Issues: User wollte keine automatische Container-Abschaltung mehr; ausserdem war "Prompt wirkt nicht" auf missverstaendliches Output-Format zurueckzufuehren.
- Loesung: `docker stop watchdog` ausgefuehrt (OWUI laeuft weiter healthy), Status in `README.md` + `watchdog/README.md` + `TODO.md` vermerkt und die Prompt-Normalisierung als simples "Uebersetzen ins Standardformat" beschrieben.

## 2026-02-04
- Aufgabe: Prompt-V2 technisch durchgezogen: keine nachtraegliche Umschreibung der Summary-Dateien mehr.
- Probleme/Bugs/Issues: Bisher wurde der LLM-Output in kanonische Legacy-Sections umgeformt; dadurch sah das Ergebnis "alt" aus und war fuer Prompt-Arbeit nicht nachvollziehbar.
- Loesung: `summarize_transcript_ref` speichert jetzt den Prompt-Output direkt; Summary-Validierung, Progress-Checks und Aggregation wurden auf Dual-Format (Legacy + Wrapped Docs) erweitert, damit der Rest der Pipeline weiter funktioniert.

## 2026-02-04
- Aufgabe: Die 10 zuletzt geladenen Transcripts auf das neue Summary-Schema (Prompt V2 Wrapped Docs) umgestellt.
- Probleme/Bugs/Issues: Initiale Regeneration zeigte weiter altes Format, weil bestehende Summary-Dateien als gueltig erkannt und daher uebersprungen wurden (kein Re-Write bei vorhandenen validen Files).
- Loesung: Die 10 betroffenen `*.summary.md` Dateien wurden zuerst in `*.summary.pre_v2_backup_<ts>.md` umbenannt und danach gezielt per `summarize_transcript_ref` neu erzeugt; Verifikation via `rg '<<<DOC_START>>>'` ergab 10/10 im neuen Schema.
