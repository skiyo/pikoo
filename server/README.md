# Pikoo Agent server

**English** | [简体中文](README.zh-CN.md) · [Project](../README.md)

The server connects Pikoo’s device to a realtime voice model and manages sessions, family memory and configured tools. It composes the pinned `qwen-audio-agent@2.0.1` runtime with Pikoo adapters; it is separate from the model generating speech.

This guide is for server developers and operators. Start with the [offline simulator](../docs/getting-started.md) if you only want to see the eyes. Detailed host installation, certificate, pairing, backup and recovery procedures are retained in the [Chinese operations guide](operations.zh-CN.md).

## Enclosure printing resources

The three original cat-enclosure STLs, print order, illustrated assembly guide and checklist are in the [enclosure directory](../hardware/enclosure/README.md). The project family reports successful printing, assembly and home use (2026-10-27); that hardware feedback is separate from this module’s software/research checks.

Native OpenAI Live + Terra preview: [English](../docs/openai-live.md) | [简体中文](../docs/openai-live.zh-CN.md). Follow that guide for the new environment file and continuous-audio clients; existing Gemini instructions remain for an explicitly selected deployment. There is no automatic provider fallback.

## Components

| File or directory | Responsibility |
|---|---|
| `openai-live.mjs`, `live-runtime.mjs`, `openai-terra.mjs` | Native Live transport, continuous playback, Terra delegation and text model calls |
| `live-idle.mjs`, `live-usage.mjs` | Semantic idle, private usage accounting and local diagnostics |
| `host.mjs` | Compose the runtime and Pikoo adapters |
| `google-live-compat.mjs` | Gemini Live event/tool compatibility, activity-detection options and connection time context |
| `context-runtime.mjs`, `context-learning.mjs`, `memory-timeout.mjs` | Recent context, durable background learning, summaries and bounded text-call deadlines |
| `deepseek-search.mjs`, `family-tools.mjs` | Configured search, public-page reading and family-list tools |
| `companion-runtime.mjs`, `silence-output.mjs` | Optional selective response and native silence-marker handling |
| `provider-check.mjs`, `time-context.mjs` | Provider diagnostics and server-generated time context |
| `deploy/`, `persona/` | Sanitized deployment and persona templates |
| `reports/` | Dated verification evidence, distinct from current service health |

## Install and check

Use Node.js 24+ and run these commands from the repository root:

```sh
(cd server && npm ci --ignore-scripts)
(cd server && npm test)
```

The tests do not require provider credentials. `npm start` inside `server/` runs `host.mjs`; a live service additionally needs its own private runtime configuration, provider credentials and issued device tokens. Follow the operations guide before exposing a gateway.

The recorded host setup uses Alibaba Cloud Linux 4 and a dedicated `pikoo` service user. Paths such as `/opt/pikoo/app/` and `/var/lib/pikoo/qwaudio/` are deployment conventions, not directories created by `npm ci`. Replace all example addresses, including `203.0.113.10`.

## Configure a live service

1. Prepare private configuration from [`deploy/config.env.example`](deploy/config.env.example), selected by `QWAUDIO_CONFIG_DIR`. Keep `config.env` owner-readable only and fill persona templates separately.
2. Use a compatible realtime provider. Current Pikoo adapters target Gemini Live; text-model calls handle memory extraction and summaries. Review compatibility before changing the pinned runtime or provider.
3. Install the systemd and Nginx templates for your host. Validate certificate trust, WebSocket forwarding and the actual service user’s egress before pairing a device.
4. Issue a separately revocable credential per device, then connect the simulator or board using the resulting private configuration.

Provider keys and household profiles stay on the server. Device/browser configuration must contain only its own endpoint and device credential. Keep proxy control ports and the internal gateway private. The [operations guide](operations.zh-CN.md) provides the exact host commands and recovery sequence.

## Memory, tools and response policy

| Concern | Authoritative guide |
|---|---|
| Current-topic restoration, long-term memory, past-topic recall and retry limits | [Context and memory](../docs/context-memory.md) |
| Search, public-page reading, family lists and service configuration | [Family tools](../docs/family-tools.md) |
| When to speak, expected silence and explicitly enabled companion mode | [Quiet companion mode](../docs/companion.md) |
| End, sleep, reconnect and playback cancellation | [Conversation lifecycle](../docs/conversation-lifecycle.md) |

The committed deployment template keeps `AGENT_PROTOCOL=none`; describing Pikoo as an AI Agent does not require enabling a separate backend Agent. Search uses its configured adapter. MCP is an extension interface, not a claim that weather, smart-home or MCP OAuth services are enabled by default. Preserve the existing dependency/security review before enabling additional flows.

The current persona policy replies in Mandarin Chinese. The bilingual documentation does not promise bilingual spoken output.

## Operate and maintain

Back up private configuration, memory, history, topic digests and the learning outbox together. Restore in an isolated directory first; a rollback must not overwrite newer family data. Pairing output contains a credential and belongs in a protected file, not an issue or commit.

Use the installed `pikoo-admin` helper through SSH for health, device revocation, restart and backup. A successful software test or model call does not establish real-device listening quality or long-duration acceptance. See [validation records](../docs/validation-summary.md) and [Security](../SECURITY.md).
