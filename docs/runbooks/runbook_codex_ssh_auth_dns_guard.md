# Runbook: Codex/VSC SSH Auth DNS Guard

Ziel: Verhindern, dass Codex Login in VS Code Remote SSH wegen DNS-Fehlern (`auth.openai.com`) erneut ausfaellt.

## Root Cause (kurz)
- Wenn Tailscale DNS Override aktiv ist (`accept-dns=true`), landet `/etc/resolv.conf` auf `100.100.100.100`.
- In diesem Setup lieferte der Resolver zeitweise `SERVFAIL` fuer Public DNS.
- Ergebnis: OAuth Token Exchange gegen `https://auth.openai.com/oauth/token` scheitert.

## Guard-Komponenten
- Check: `scripts/check_codex_auth_dns.sh`
  - prueft `tailscale CorpDNS`, DNS-Aufloesung, OAuth-Endpoint-Erreichbarkeit
- Remediation: `scripts/remediate_codex_auth_dns.sh`
  - setzt idempotent `tailscale set --accept-dns=false`
  - verifiziert danach den Healthcheck erneut
- Persistenz: `scripts/install_codex_auth_dns_guard_cron.sh`
  - installiert User-Cronjobs (`@reboot` + alle 10 Minuten Check)

## Installation
1. Guard installieren:
   - `./scripts/install_codex_auth_dns_guard_cron.sh`
2. Cron pruefen:
   - `crontab -l`
3. Soforttest:
   - `./scripts/check_codex_auth_dns.sh`

## Verifikation (Soll)
- `tailscale debug prefs | jq -r '.CorpDNS'` => `false`
- `/etc/resolv.conf` nutzt LAN/Host DNS (nicht `100.100.100.100`)
- `getent hosts auth.openai.com` liefert IPs
- `curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://auth.openai.com/oauth/token` liefert `400` (ohne Body erwartet)

## Log / Troubleshooting
- Log-Datei: `${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/codex-auth-dns-guard.log`
- Letzte Eintraege:
  - `tail -n 50 ${XDG_STATE_HOME:-$HOME/.local/state}/ai_stack/codex-auth-dns-guard.log`
- Manuelle Remediation:
  - `./scripts/remediate_codex_auth_dns.sh --reason manual`

## Rollback
- Cron Guard entfernen:
  - `crontab -l | awk 'index($0,\"# BEGIN AI_STACK_CODEX_AUTH_DNS_GUARD\")==1{skip=1;next} index($0,\"# END AI_STACK_CODEX_AUTH_DNS_GUARD\")==1{skip=0;next} !skip{print}' | crontab -`
- Optional DNS Override wieder aktivieren:
  - `tailscale set --accept-dns=true`

Hinweis: Wenn `accept-dns=true` wieder aktiviert wird, kann der Auth-Fehler zurueckkommen, solange Tailscale DNS Upstream instabil ist.
