# Service configuration

**English** | [简体中文](configuration.zh-CN.md)

Copy [the example](../examples/device.example.json) outside Git. Configuration version is `1`; filenames and paths are yours. Validate without touching hardware:

```sh
python tools/configure.py --config /private/pikoo.json --dry-run
python tools/device.py configure --port PORT --config /private/pikoo.json
```

`device.py configure` sends the full configuration through USB and reboots. It does not reflash the application or overwrite the volume, orientation or family partitions. `configure.py --init /private/pikoo.json` is an optional interactive creator; secrets are entered without echo. Never commit a completed configuration.

| Section | Fields |
|---|---|
| `wifi` | `ssid`, `password` (empty for an open network) |
| `agent` | `name`, `language`, `instructions`; defaults to Pikoo / en when omitted |
| `live` | `protocol`, full `url`, `api_key`, `model`, `voice` (marin), `audio_rate` (16000 or 24000) |
| `llm` | `protocol`, full `url`, `api_key`, `model` |
| `search` | `enabled`; if enabled: `protocol`, full `url`, `api_key`, and `model` for Responses; optional Tavily `extract_url` |
| `network` | Optional `proxy_url` (HTTPS origin) and `proxy_basic` (Base64 username:password) |

No API paths are appended. Empty `api_key` omits Authorization for services that intentionally require no authentication; otherwise Bearer authentication is used. Keys are independent and are never copied from one service to another. Proxy Basic authentication is separate. All service connections use certificate verification. There is no insecure-TLS switch.

## Supported protocols

- `live.protocol = openai_live`: primary Live WebSocket, client delegation, input/output transcript events, PCM16 audio and Decisions interaction triggers. OpenAI's endpoint is `wss://api.openai.com/v1/live/sessions`; compatible endpoints must support these capabilities. Configure the account's Live model and voice explicitly.
- `llm.protocol = openai_responses`: Responses API with function calls and completed output; OpenAI's endpoint is `https://api.openai.com/v1/responses`.
- `llm.protocol = openai_chat_completions`: Chat Completions with function tools, tool result messages and non-streamed responses. A service merely accepting chat messages is insufficient.
- `search.protocol = tavily`: Search API; typical endpoint `https://api.tavily.com/search`. Set `extract_url` to `https://api.tavily.com/extract` to enable webpage extraction. It must have the same origin as the search endpoint because it uses that key.
- `search.protocol = openai_responses`: an independently configured Responses endpoint/model with hosted `web_search` capability. Results include available source citations; this adapter does not expose arbitrary webpage extraction.

Search is off in the example and requires no key until enabled. URL changes select a compatible deployment, not a different wire protocol. Unknown protocol IDs are rejected. Custom CA and alternative authentication header schemes are not implemented.

[Official Live delegation](https://developers.openai.com/api/docs/guides/live-delegation) · [Responses search](https://developers.openai.com/api/docs/guides/tools-web-search) · [Tavily API](https://docs.tavily.com/)

The default conversation language is English (`en`). Set `agent.language` to `zh-CN` for Chinese, then update the configuration over USB; no firmware rebuild is required.

`tools/usb-setup.py --language zh-CN` / `tools/configure.py --init /private/pikoo.json --language zh-CN`: Chinese setup prompts; the default UI language is English.
