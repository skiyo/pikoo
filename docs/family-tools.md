# Search, web reading and family lists

**English** | [简体中文](family-tools.zh-CN.md) · [Architecture](architecture.md)

Pikoo uses Gemini Live to select tools and speak the answer. The pinned Qwen Audio 2.0.1 runtime executes them. `AGENT_PROTOCOL=none` remains unchanged: this is not a separate backend agent or a new conversational LLM.

| Tool | Implementation | Persistence / cost |
|---|---|---|
| `web_search` | Pikoo's injected DeepSeek Search Provider | Calls the official raw Search endpoint; the account's current billing applies |
| `fetch_url` | Upstream `SafeUrlFetcher` | Direct public-page request; does not call DeepSeek Fetch |
| `notes` | Upstream family-owner list store | Private `frontend-notes.json`, survives restart |
| Memory, recall, current time | Existing runtime | See [context and memory](context-memory.md) |

## Configuration and behavior

Enable `QWEN_AUDIO_WEB_TOOLS_ENABLED=on` and `QWEN_AUDIO_NOTES_TOOL_ENABLED=on`. Keep `QWEN_AUDIO_WEB_SEARCH_PROVIDER=none`: Pikoo explicitly injects its adapter, so no 360/Bing fallback is created. Store `DEEPSEEK_API_KEY` only in the protected server configuration, never in firmware, browser configuration or public files. With no key, search is unavailable; web reading and lists remain usable.

Search uses `POST https://api.deepseek.com/v1/tools/search`, a 1–128 Unicode-character query, five results by default (up to eight) and `need_content=false`. The provider maps summaries and dates into native citations, limits the raw response to 256 KiB and uses an eight-second deadline. It does not send full conversations, household profiles or a localization IP. It does not retry automatically or call a DeepSeek language model. Authentication, insufficient balance, rate limiting, malformed results, timeout and network errors have distinct sanitized codes. An error or no results is not a successful factual answer.

Web reading accepts public HTTP/HTTPS textual pages, with private-network and redirect validation, a 1 MiB response limit and up to 12,000 returned characters. It does not bypass logins, paywalls or browser challenges. External content is untrusted evidence, not permission to modify lists or instructions to follow. Audio/text responses retain the Mandarin/English policy. Cancelled or interrupted Google tool calls cannot submit late results that would restart native speech.

Lists support create-by-add, show, remove, clear and drop. Names and items use the upstream ambiguity rules; the assistant asks instead of choosing between matching lists. Lists belong to the existing family owner, not an inferred speaker, and do not automatically become durable family facts. Confirm a change only after a successful tool result.

## Operations and verification

Deploy `deepseek-search.mjs` and `family-tools.mjs` alongside `host.mjs` and the existing adapters. Update the private persona's old capability statement without replacing household data. Back up configuration and code before restarting; include the notes file in normal private-state backups. Rollback must not overwrite lists or memories created after deployment.

Run `(cd server && npm test)` and `node --test firmware/simulator/*.test.mjs`. Real-provider acceptance uses a separate loopback gateway and owner, with separate configuration/data/state, discarded generated audio and no device takeover. Model tests and hardware listening acceptance are recorded separately. Search billing is independent of Live billing: [DeepSeek documentation](https://api-docs.deepseek.com/zh-cn/guides/search/). Upstream mechanisms: [search](https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/docs/guides/web-search.md), [lists](https://github.com/QwenAudio/qwen-audio-agent/blob/v2.0.1/docs/guides/notes-reminders.md).

2026-10-20 acceptance: 27 server checks and 23 simulator regressions passed. Phased real-provider checks covered Mandarin/English search (five citations each), public-page reading (one citation per page), list creation, ambiguity, persistence across a gateway restart, removal/deletion and an honest failed-search reply. The final short-tool configuration uses Google's `BLOCKING` declarations for `web_search`, `fetch_url` and `notes`; five real scenarios were rechecked with that configuration. Actual network/account failures were retained as failures before successful calls were verified. Deployment health confirmed both retrieval capabilities and notes enabled, backend disabled, and household memory/profile documents unchanged. The isolated gateway was stopped and its credentials removed. No board was operated or flashed; hardware listening acceptance remains pending.
