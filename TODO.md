# TODO / Active Backlog

Purpose: Active work only.
Contains: Open tasks with priority and status.
Does not contain: Completed history (see Git/ADR/CHANGELOG).

## P0 (Now)
- [ ] **Docs strategy finalization (root main docs)**
  - Align all root docs to target model:
    - `AGENTS.md` (rules only)
    - `README.md` (operator guide)
    - `INDEX.md` (navigation)
    - `HANDOFF.md` (snapshot)
    - `TODO.md` (active only)
    - `CHANGELOG.md` (short, user/release relevant)
    - `docs/adr/` (decision records)
  - DoD: no duplicate paragraph across these files.

- [ ] **ChangeLog rebaseline**
  - Reformat to Keep a Changelog style (`Added/Changed/Fixed/Breaking`).
  - Keep only release/user-visible entries.
  - DoD: concise file, old detail discoverable via Git history.

- [ ] **Open WebUI Knowledge cleanup (pending user confirm)**
  - Remove undesired collections (`bitcoin` / `crypto`) only after explicit confirmation.
  - Re-verify intended topics and sync behavior.

- [ ] **Backup disk cleanup**
  - Delete large backup files under `/srv/ai-stack/backups/` (user-intended cleanup).
  - Command (requires sudo): `sudo rm /srv/ai-stack/backups/owui-data__*.tar.gz`
  - DoD: free disk space validated before/after.

## P1 (Next)
- [ ] **Fourier analysis deepening (FRED + Yahoo)**
  - Define first target basket (symbols/series).
  - Add significance/robustness checks (beyond raw DFT ranking).
  - Document interpretation guardrails for non-forecast use.

- [ ] **Define `atlas` explicitly**
  - Add authoritative definition/location in `HANDOFF.md` and (if needed) ADR.
  - DoD: `atlas` survives context resets without ambiguity.

- [ ] **OpenClaw Telegram E2E final verification**
  - Close DM/group behavior verification and record final operational path.

## P2 (Later)
- [ ] **Resource checks automation**
  - Periodic free-space + backup growth checks.
  - Alert thresholds for critical disk pressure.

## ai_stack_todo
- Active list lives in this file only.
- Completed items are removed (history in Git/ADR/CHANGELOG).
