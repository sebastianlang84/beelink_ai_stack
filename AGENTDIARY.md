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
- Aufgabe: TODO fuer Apache Tika Docker-Installation ergaenzt.
- Probleme/Bugs/Issues: Keine.
- Loesung: TODO-Item in `TODO.md` erfasst; CHANGELOG aktualisiert.
