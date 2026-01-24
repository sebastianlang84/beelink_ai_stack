# Watchdog/Monitoring Ideen (Plan, kein Code)

Ziel: Ein leichter Waechter, der CPU-Last, Temperatur und Festplattenspeicher beobachtet, Ursacheingrenzung erleichtert und im Fehlerfall kurze, verwertbare Diagnosen ablegt.

## 1) Scope & Prinzipien
- Host-first Monitoring (nicht nur Container), weil Temperatur/Disk hostbezogen sind.
- Minimal invasive, kein Dauer-Profiler; Sampling in festen Intervallen.
- Keine Secrets im Output; Logs/Artefakte klar rotieren.
- Umsetzung als eigener Container (Watchdog) mit read-only Zugriff auf Host `/proc`, `/sys`, `/` und Docker Socket.

## 2) Metriken (Minimal-Set)
### CPU
- Host CPU % (gesamt + top 5 Prozesse)
- Optional: Container CPU % (top 3)
- Load Average (1/5/15)
- Optional: PSI (Pressure Stall Information) fuer CPU/IO/Mem (`/proc/pressure/*`)

### Memory & Swap (Optional)
- Host MemAvailable, SwapFree
- OOM-Hinweise (letzte Kernel-Messages, falls zulaessig)

### Temperatur
- CPU Package Temp (sofern via `sensors`/`/sys` verfuegbar)
- Optional: Mainboard oder SSD Temp (falls Sensors liefern)

### Festplatte/Storage
- Host Root FS Belegung (%/frei) + Growth-Delta seit letztem Sample
- Docker Volumes: Groesse/Top Wachstum (sofern schnell messbar)
- Inode-Auslastung (df -i), sonst "voll" trotz freiem Speicher
- Optional: /proc/diskstats Delta (reads/writes) fuer IO-Spikes

### Docker Hygiene (Optional, Periodisch)
- Stopped/Exited Container (Anzahl + Liste)
- Orphaned Container (nicht in Compose registriert)
- Dangling Images (Anzahl + Groesse)
- Unused Images (Top Groesse)
- Unused Volumes/Networks (Anzahl)
- Docker Build Cache Groesse
- Log-Size pro Container (Top 3)
- Optional: `docker system df` Snapshot (Summen fuer Images/Volumes/Cache)

## 3) Sampling & Trigger
- Normalbetrieb: alle 30-60s kurz messen und nur aggregieren (z. B. 5-min window).
- Energiespar-Variante: Baseline alle 15-30 Minuten, Details nur bei Trigger.
- Trigger: wenn CPU > X% fuer Y Sekunden ODER Temp > T ODER Disk > D%.
- Bei Trigger: "Burst-Logging" fuer N Sekunden (z. B. 10-30s) mit Detaildaten.
- Trigger-Logik robust: consecutive samples + Hysterese + Cooldown (z. B. 5-10 min)

## 4) Diagnostik-Artefakte (bei Trigger)
- Kurzprofil der Top-Prozesse (PID, CMD, CPU, MEM)
- Containerstats (owui, tm, context6, qdrant) mit CPU/Mem
- Optional: py-spy Snapshot von `owui` falls CPU > X% (nur bei Bedarf)
- Letzte 100 Zeilen relevanter Logs (owui + MCP)
- Optional: timestamped Bundle (summary.json, top_procs.txt, docker_stats.json, logs_tail/)

## 5) Alerts & Aktionen
- Alert-Kanaele: lokale Log-Datei + optional Push (Tailscale Notify / Mail/SMTP / Telegram / Discord / ntfy)
- Optionale Auto-Aktion: "degradieren" (z. B. Tool-Connections aus) erst nach manueller Freigabe
- Auto-Aktion (implementiert): Temp-Schutz stoppt definierte Container nach X Messungen ueber Schwellwert
- Alternative (nicht implementiert): zuerst CPU-Limit setzen (z. B. 50%) fuer 10-15 Minuten, erst bei weiterem Anstieg stoppen
- Safety: Docker-Socket ist Root-aehnlich, nur mounten wenn Container-Stats benoetigt werden

## 6) Schwellwerte (Startwerte, Vorschlag)
Hinweis: Intel N150 (Tjunction 105C, Base Power 6W) im Mini-PC-Gehaeuse. Ziel ist Stabilisierung vor dauerhaftem Throttling.

Signal | Warn | Crit | Action
--- | --- | --- | ---
CPU (gesamt) | >85% fuer 120s | >95% fuer 180s | optional (nur mit Temp/Disk kombiniert)
Load avg (1m) | >4.0 fuer 5m | >6.0 fuer 5m | diagnostisch
CPU Temp | >85C fuer 60s | >92C fuer 60s | stop bei >95C fuer 3 Messungen
Disk root FS | >80% | >90% | ab 95%: panic (nur Alerts)
Disk Growth | >+1 GB/10 min | >+5 GB/10 min | Trigger: Top Wachstum
PSI IO (some avg10) | >5% fuer 2m | >10% fuer 2m | priorisiere Disk-Artefakte

## 7) Ablage & Rotation
- Logs unter `/srv/ai-stack/monitoring/` (gitignored)
- Rotation: z. B. max 7 Tage oder max 500 MB
- Regel: Trigger-Artefakte separat speichern (timestamped)

## 8) Offene Fragen
- Schwellenwerte: CPU/Temp/Disk (konkret fuer AZW MINI S)
- Bedarf an Langzeit-Historie (Prometheus/Grafana vs. lightweight files)
- Einfache UI gewuenscht? (HTML Dashboard / CSV)
