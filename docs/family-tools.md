# Tools

**English** | [简体中文](family-tools.zh-CN.md)

`family_list` manages `shopping` and `todo`; `family_memory` manages `memory`. Operations are `list`, `add`, `remove`, `replace`, `clear`. Changes use exact entry text; `replace` needs a replacement; `clear` requires `confirmed=true`. Arguments are bounded and validated before committing.

`web_search(query)` uses the configured search adapter and returns bounded facts with sources. Tavily extraction additionally registers `read_webpage(url)` for HTTPS URLs. Retrieved text is untrusted reference material and cannot replace Agent instructions. Service failures return errors to reasoning, rather than fabricated results. API redirects are not followed.

Register extensions through a schema and executor in the shared core, then add failure, cancellation and persistence tests. A tool schema is not evidence of an integrated external product.

## Local operations

| Operation | Behavior to verify |
|---|---|
| `list` | Return the chosen collection without changing it |
| `add` | Validate and save an entry within capacity |
| `remove` | Match the exact stored text; do not guess a similar entry |
| `replace` | Require an exact target and a replacement |
| `clear` | Require explicit confirmation before deleting the collection |

For example, “replace apples with green apples” needs both strings; “remove the thing I mentioned” may require clarification. Tool errors must preserve the distinction between validation failure, capacity exhaustion and backend failure. The state and write receipt commit together; if the final spoken acknowledgement is lost, read back the collection rather than assuming it failed.

## Body tools

Agent tools, USB and buttons share one C++ body controller. The model tool list comes from the executor registry, with the same schemas for Responses and Chat Completions. Voice routing combines transcript fragments and preserves negation/quotation tails. Keywords select a reasoning task, never directly execute hardware. The [user guide](usage.md) defines everyday commands and duration rules.

| Logical interface / wire name | Arguments and result |
|---|---|
| `body.get_state` / `body_get_state` | No arguments; actual gain, volume scale, backlight, session, microphone and temporary expression/gaze |
| `body.set_audio` / `body_set_audio` | Integer `value`; `mode` is `gain_db`, `delta_db` or `percent` |
| `body.set_display` / `body_set_display` | Integer `value`; `mode` is `percent` or `delta_percent`; both eyes change together |
| `body.perform` / `body_perform` | `action` and optional `duration_ms`; finite expression, blink, gaze and session actions |

Absolute codec gain is −50…0 dB. Percentages are integers 0…100, mapped by `round(-50 + percent/2)`. A model request is `{"mode":"delta_db","value":3}`. USB also accepts legacy single-field arguments such as `{"delta_db":3}`; conflicting fields are rejected. Brightness ranges from 0 to 100%; zero switches off only the backlights.

Actions are `happy`, `curious`, `drowsy`, `neutral`, `blink`, `blink_left`, `blink_right`, `look_left`, `look_right`, `look_front`, `stop_speaking`, `sleep`, `mute_microphone`. `duration_ms` applies to expressions and gaze, up to 10000 ms; a blink always lasts 350 ms.

```sh
python tools/body.py --port PORT --id volume-request-1 body_set_audio '{"mode":"delta_db","value":3}'
python tools/body.py --port PORT body_perform '{"action":"happy","duration_ms":3000}'
```

`applied` confirms a setting/action was applied; `saved` confirms preference persistence. Temporary actions normally return `saved:false`. `persistence_failed` means applied now but possibly lost on restart; `hardware_failed` is not success. Each applied step immediately supplies verified progress to voice; later reasoning failure does not erase completed receipts.

The last 64 body call receipts are process-local, unlike persistent list receipts. Same-ID retries do not repeat relative adjustments; conflicting arguments return an error, and reboot clears the cache. Manual USB commands default to new requests; explicitly reuse `--id` for a retry. Cancellation invalidates unexecuted actions without undoing applied settings. Ending a session or reconnecting clears temporary actions; volume and brightness preferences remain.

## Search is external information

Search results can be stale, incomplete or malicious. Retain source links where available and treat page text as reference material, never instructions to reveal secrets or modify unrelated data. Extraction support is explicit; it is not implied by having search enabled. The [configuration reference](configuration.md) lists the required settings. No arbitrary shell, filesystem or home-automation executor is bundled.
