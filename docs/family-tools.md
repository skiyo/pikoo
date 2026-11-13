# Tools

**English** | [简体中文](family-tools.zh-CN.md)

`family_list` manages `shopping` and `todo`; `family_memory` manages `memory`. Operations are `list`, `add`, `remove`, `replace`, `clear`. Changes use exact entry text; `replace` needs a replacement; `clear` requires `confirmed=true`. Arguments are bounded and validated before committing.

`web_search(query)` uses the configured search adapter and returns bounded facts with sources. Tavily extraction additionally registers `read_webpage(url)` for HTTPS URLs. Retrieved text is untrusted reference material and cannot replace Agent instructions. Service failures return errors to reasoning, rather than fabricated results. API redirects are not followed.

Register extensions through a schema and executor in the shared core, then add failure, cancellation and persistence tests. A tool schema is not evidence of an integrated external product.

## Tool execution contract

## Local operations

| Operation | Behavior to verify |
|---|---|
| `list` | Return the chosen collection without changing it |
| `add` | Validate and save an entry within capacity |
| `remove` | Match the exact stored text; do not guess a similar entry |
| `replace` | Require an exact target and a replacement |
| `clear` | Require explicit confirmation before deleting the collection |

For example, “replace apples with green apples” needs both strings; “remove the thing I mentioned” may require clarification. Tool errors must preserve the distinction between validation failure, capacity exhaustion and backend failure. The state and write receipt commit together; if the final spoken acknowledgement is lost, read back the collection rather than assuming it failed.

## Search is external information

Search results can be stale, incomplete or malicious. Retain source links where available and treat page text as reference material, never instructions to reveal secrets or modify unrelated data. Extraction support is explicit; it is not implied by having search enabled. The [configuration reference](configuration.md) lists the required settings. No arbitrary shell, filesystem or home-automation executor is bundled.
