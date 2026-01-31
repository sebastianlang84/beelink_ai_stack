# OpenClaw install + Telegram notes (sources)

Purpose: record official install commands and Telegram setup pointers for later reference.

## Official install commands (from docs)

PowerShell (Windows):

```
iwr -useb https://openclaw.ai/install.ps1 | iex
```

Global npm install:

```
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

Linux/macOS installer (recommended):

```
curl -fsSL https://openclaw.bot/install.sh | bash
```

Install from git via installer:

```
curl -fsSL https://openclaw.bot/install.sh | bash -s -- --install-method git
```

## Telegram channel setup (high-level)

Key points to confirm in the official docs:
- Bot token via BotFather
- Configure token via env or config
- DM policy defaults to pairing
- Group mention gating recommended (requireMention)
- Optional config protection (block config writes)

## Sources

- https://docs.openclaw.ai/install/index
- https://docs.openclaw.ai/install/installer
- https://docs.openclaw.ai/channels/telegram
- https://docs.openclaw.ai/gateway/configuration
