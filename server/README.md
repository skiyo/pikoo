# Pikoo Gateway

Local Agent devices require only Mihomo. This page retains compatibility Gateway setup and rollback. See [local Agent deployment](../docs/local-agent.zh-CN.md).

**English** | [简体中文](README.zh-CN.md)

## Requirements

Node.js 24+, a persistent private directory, an HTTPS/WSS reverse proxy, OpenAI API access to **gpt-live-1** and **gpt-6.1-terra**, and optional DeepSeek Search access. The runtime dependency is pinned to `qwen-audio-agent@2.0.1`. Model services are external and may charge; `npm ci` does not provide their credentials.

```sh
(cd server && npm ci --ignore-scripts)
(cd server && npm test)
mkdir -p "$HOME/.config/pikoo/qwaudio"
chmod 700 "$HOME/.config/pikoo/qwaudio"
cp server/deploy/config.env.example "$HOME/.config/pikoo/qwaudio/config.env"
chmod 600 "$HOME/.config/pikoo/qwaudio/config.env"
```

Edit that private file: OpenAI key, optional search key, allowed HTTPS origin and service settings. Put family-specific persona files under the configured runtime directory, starting from `server/persona/` templates; do not replace live family data during upgrades. Environment must be loaded **before** importing `host.mjs`:

```sh
QWAUDIO_CONFIG_DIR="$HOME/.config/pikoo/qwaudio" \
node --env-file="$HOME/.config/pikoo/qwaudio/config.env" server/host.mjs
```

Use a service user and systemd for a hosted deployment. Adapt the templates in `server/deploy/` to your host; the shipped systemd path assumes server files live directly at `/opt/pikoo/app/`. Add an `EnvironmentFile` for the protected runtime file. Nginx forwards HTTPS and WebSocket Upgrade to 127.0.0.1:3101. Restrict allowed origins, expose no internal proxy or management listener, and verify TLS trust and egress as the actual service user. A domain certificate is simplest; IP certificates require operator-managed short-interval renewal.

## Pair a device

With the Gateway running and the same private config directory:

```sh
QWAUDIO_CONFIG_DIR="$HOME/.config/pikoo/qwaudio" \
server/node_modules/.bin/qwenaudio gateway pair --name living-room --endpoint https://YOUR_HOST --json
```

The result contains a **secret device credential**. Save it privately. Use `gateway devices --json` and `gateway revoke DEVICE_ID` with the same runtime to list/revoke. Supply each device only its endpoint and token, never the provider API key. Management belongs behind SSH.

## Modules

| Module | Role |
|---|---|
| `host.mjs` | Runtime composition, lease and shutdown |
| `openai-live.mjs`, `live-runtime.mjs` | Native Live transport, 16 kHz audio, delegation and continuous playback |
| `openai-terra.mjs`, `live-idle.mjs` | Responses reasoning, interaction classification and idle |
| `context-runtime.mjs`, `context-learning.mjs` | Text restoration, summaries, memory queue and retry |
| `family-tools.mjs`, `deepseek-search.mjs` | Safe web reading, search and shared notes |
| `live-usage.mjs` | Private usage ledger and local diagnostics |

[Live behavior](../docs/openai-live.md) · [Memory](../docs/context-memory.md) · [Tools](../docs/family-tools.md) · [Operations](operations.zh-CN.md)

## Back up and recover

Stop the Gateway, back up its complete private config/state tree plus the deployed source/version, then restart. Configuration, owner records, device credentials, recent history, topic digests, memory, lists, call-ID reservations, learning outbox and usage belong together. Test restore in an isolated directory. Software rollback must preserve newer family memory and list data.

Do not expose `GET /api/pikoo/live-status` publicly; use SSH/local access. Diagnose provider auth, quota, proxy/TLS, device uplink and playback separately. A healthy HTTP endpoint does not prove speech quality.
