# Runbook — Transcript Miner Lifecycle Maintenance (Download-unabhaengig)

Ziel: Cleanup/Rotation von `investing_new`/`investing_archive` und Cold-Storage **ohne neue Downloads**.

Umsetzung:
- Maintenance Script: `scripts/maintain-investing-lifecycle.sh`
- Freshness Guard: `scripts/check-hot-summaries-freshness.sh`
- systemd Templates:
  - `scripts/systemd/ai-stack-tm-investing-maintenance.service`
  - `scripts/systemd/ai-stack-tm-investing-maintenance.timer`

## 1) Wichtige Abgrenzung

- Dieser Maintenance-Flow ist absichtlich getrennt von Download-Runs.
- Der Kill-Switch `schedulers.disabled` blockiert Run-/Backup-Scripts, aber **nicht** dieses Maintenance-Script.

## 2) Manuelle Nutzung

Nur Guard-Check:
```bash
./scripts/maintain-investing-lifecycle.sh check
```

Nur Lifecycle-Sync:
```bash
./scripts/maintain-investing-lifecycle.sh sync
```

Sync + Guard (empfohlen):
```bash
./scripts/maintain-investing-lifecycle.sh ensure
```

Hinweis zum `ensure`-Ablauf:
1. Lifecycle-Sync (`/sync/lifecycle/investing`)
2. Orphan-Prune: stale hot summaries, die nicht mehr im aktuellen `indexes/investing/current/transcripts.jsonl` stehen, werden nach `cold` verschoben.
3. Freshness-Guard

Dry-Run (keine Mutationen, danach Guard):
```bash
./scripts/maintain-investing-lifecycle.sh dry-run
```

## 3) Timer installieren

```bash
sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing-maintenance.service /etc/systemd/system/
sudo cp /home/wasti/ai_stack/scripts/systemd/ai-stack-tm-investing-maintenance.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-stack-tm-investing-maintenance.timer
```

Status:
```bash
systemctl status ai-stack-tm-investing-maintenance.timer --no-pager
systemctl list-timers --all | rg 'ai-stack-tm-investing-maintenance'
```

## 4) Guard-Schwelle

Default:
- `HOT_MAX_AGE_DAYS` wird aus `transcript-miner/config/config_global.yaml` gelesen (`archive_max_age_days`).

Optional manuell ueberschreiben:
```bash
HOT_MAX_AGE_DAYS=15 ./scripts/check-hot-summaries-freshness.sh
```

## 5) Troubleshooting

- Service-Logs:
```bash
sudo journalctl -u ai-stack-tm-investing-maintenance.service -n 200 --no-pager
```

- Guard direkt:
```bash
./scripts/check-hot-summaries-freshness.sh
echo $?
```

Exit Codes Guard:
- `0`: keine stale files
- `3`: stale hot summaries gefunden
- `4`: Pfade fehlen
- `5`: Config/Parse-Fehler
