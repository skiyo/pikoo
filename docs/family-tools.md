# Tools

**English** | [简体中文](family-tools.zh-CN.md)

`family_list` manages `shopping` and `todo`; `family_memory` manages `memory`. Operations are `list`, `add`, `remove`, `replace`, `clear`. Changes use exact entry text; `replace` needs a replacement; `clear` requires `confirmed=true`. Arguments are bounded and validated before committing.

`web_search(query)` uses the configured search adapter and returns bounded facts with sources. Tavily extraction additionally registers `read_webpage(url)` for HTTPS URLs. Retrieved text is untrusted reference material and cannot replace Agent instructions. Service failures return errors to reasoning, rather than fabricated results. API redirects are not followed.

Register extensions through a schema and executor in the shared core, then add failure, cancellation and persistence tests. A tool schema is not evidence of an integrated external product.
