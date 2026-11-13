# Configuration reference

**English** | [简体中文](configuration.zh-CN.md)

Configuration is a complete versioned JSON document, stored privately outside Git and provisioned over USB. Start from [device.example.json](../examples/device.example.json). Example domains and `YOUR_...` strings are placeholders, not operational service settings.

## Lifecycle

1. Copy the example or run `python tools/configure.py --init /absolute/private/device.json`.
2. Fill Wi-Fi, Live and reasoning settings. Leave search disabled until needed.
3. Run `python tools/configure.py --config /absolute/private/device.json --dry-run`.
4. Run `python tools/device.py configure --port PORT --config /absolute/private/device.json`.
5. Inspect status and unmute when ready. This command provisions and reboots without reflashing the application.

Supply the complete configuration on each update; this is not a partial JSON patch. Store the source file securely so key rotation or network changes are repeatable. Validation makes no API calls. Settings use ordinary replaceable `agent_secret` NVS; family exports exclude them.

## Fields and limits

Limits on ordinary strings are UTF-8 bytes unless stated otherwise. The normalized complete document is limited to 16 KiB.

| Field | Meaning and constraint |
|---|---|
| `version` | Integer `1` |
| `wifi.ssid` | Required, 1–32 bytes; use 2.4 GHz Wi-Fi |
| `wifi.password` | Empty for open network; otherwise 8–63 bytes |
| `agent.name` | 1–64 bytes; default Pikoo when the whole agent section is omitted |
| `agent.language` | 1–32 bytes; default `en`; use `zh-CN` for Chinese |
| `agent.instructions` | Optional role instructions, at most 2048 bytes |
| `live.protocol` | `openai_live` |
| `live.url` | Complete WSS endpoint, at most 2048 characters |
| `live.api_key` | Service credential; empty omits Authorization |
| `live.model` | Required provider model ID, at most 128 bytes |
| `live.voice` | Voice ID, default `marin`, at most 64 bytes |
| `live.audio_rate` | Integer `16000` or `24000`; default 16000 |
| `llm.protocol` | `openai_responses` or `openai_chat_completions` |
| `llm.url`, `api_key`, `model` | Independent full HTTPS endpoint, credential and model |
| `search.enabled` | Boolean, default false |
| `search.protocol` | When enabled: `tavily` or `openai_responses` |
| `search.url`, `api_key` | Independent full HTTPS endpoint and credential |
| `search.model` | Required for Responses search |
| `search.extract_url` | Optional Tavily extraction endpoint, same HTTPS origin as search |
| `network.proxy_url` | Optional HTTPS proxy origin, without path/query |
| `network.proxy_basic` | Optional Base64 of username:password; requires proxy URL |

API keys/proxy credentials are bounded to 1024 non-whitespace printable ASCII characters. URLs cannot embed a username/password or fragment. Do not place keys in URL query parameters. There is no custom-header or custom-CA setting. Keep the example's complete `agent` section when editing individual fields.

## Adapter compatibility

| Role | Protocol | Required behavior |
|---|---|---|
| Voice | `openai_live` | WSS, client delegation, input/output transcripts, PCM16 mono, Decisions interaction events |
| Reasoning | `openai_responses` | Responses requests, function calls, completed output and tool results |
| Reasoning | `openai_chat_completions` | Non-streamed Chat Completions, function tools and tool-result messages |
| Search | `tavily` | Search results; optional extraction configured separately |
| Search | `openai_responses` | Responses with hosted `web_search` capability and available citations |

The firmware uses the **full endpoint exactly as configured**. It does not append `/v1`, infer a protocol from a hostname or follow API redirects. A text-chat provider is not automatically a Live provider. Confirm model/voice availability and capabilities with the selected deployment; model names are intentionally not hardcoded into the example.

## Reasoning and search examples

Replace only the corresponding section of the complete private configuration. These are fragments, not complete installable files:

```json
{"llm":{"protocol":"openai_chat_completions","url":"https://llm.example.com/v1/chat/completions","api_key":"YOUR_LLM_KEY","model":"YOUR_LLM_MODEL"}}
```

```json
{"search":{"enabled":true,"protocol":"tavily","url":"https://api.tavily.com/search","extract_url":"https://api.tavily.com/extract","api_key":"YOUR_SEARCH_KEY"}}
```

```json
{"search":{"enabled":true,"protocol":"openai_responses","url":"https://search.example.com/v1/responses","api_key":"YOUR_SEARCH_KEY","model":"YOUR_SEARCH_MODEL"}}
```

Omit Tavily `extract_url` to offer search only. Disabling search removes its tool capability; no search key is required. Responses search does not register arbitrary webpage extraction.

## Transport, credentials and language

Use `network: {}` for direct verified TLS. An optional standard HTTPS CONNECT proxy can be supplied as an HTTPS origin. Proxy credentials authenticate only the outer connection; service credentials travel inside the service TLS connection. Each request builds authentication for its own service. API redirect handling is intentionally disabled to avoid forwarding credentials elsewhere.

Set `agent.language` to `zh-CN` for Chinese dialogue; leave `en` for the default English experience. The `--language` option of the interactive setup tools changes their UI prompts, independently of the configuration value. Changing a display name does not retrain the English wake phrase. Role instructions guide responses but cannot add an unimplemented tool or protocol.

[Quick start](getting-started.md) · [FAQ](faq.md) · [Security](../SECURITY.md)
