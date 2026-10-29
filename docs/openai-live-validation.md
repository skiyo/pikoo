# Live + Terra validation — 2026-10-29

[English integration guide](openai-live.md) | [中文接入说明](openai-live.zh-CN.md)

**Incomplete hardware acceptance.** This record distinguishes software tests, real paid API calls, synthetic scenes and human listening. No household recordings or provider credentials are published. The operator explicitly requested continued Live debugging without automatic Gemini rollback.

## Verified results

| Check | Observed result | Boundary |
|---|---|---|
| Native Live + Terra | Real `gpt-live-1` audio and `gpt-6.1-terra` Responses; configuration and delegation inspected | A started Live session alone was not used as proof of backend access |
| Search delegation | `current_time` and `web_search` called; five search citations observed; Chinese output | Isolated gateway and synthetic input |
| Notes | Create, read after service restart, delete, verify absence | Separate state directory; no household list edits |
| Memory | Ordinary English statement about an observing schedule led to memory calls and Chinese reply; new session after restart recalled it | Synthetic fact, isolated state |
| Correction | Stored schedule changed and was read back; spoken response also asked an unnecessary clarification | Not full conversational acceptance; deletion and restart lookup subsequently succeeded, with transport reconnects in that lookup run |
| Interaction classifier | 24/24 directed, 24/24 background, 12/12 unknown; farewell field 60/60; no deadline errors | Hand-authored synthetic cases, not household accuracy |
| Quiet idle | Retest closed after 68.021 seconds, one connection, no error/reconnect | Synthetic silent input and simulated playback status |
| Host regressions | 80 Node tests passed across the server and simulator; native audio/session tests passed with ASan/UBSan | No claim of physical AEC, latency or endurance |
| Firmware | ESP-IDF 5.5.5 builds succeeded; app-only write and digest verification passed; Wi-Fi/config/model retained | Firmware `0.3.0-live4` is diagnostic preview, not a release |
| Volume | Initially retained −2 dB; later explicitly requested 0 dB, read back with DAC register 198 | The later user instruction superseded the initial no-volume-change constraint |

## Audio failures and investigation

The first `live1` greeting was audibly abnormal. Device logs showed starvation and a server-side redundant input queue overflow. `live2` removes the second microphone pacing queue and restores 900 ms playback prefill. The user then confirmed a smooth greeting but reported intermittent subsequent speech. This does **not** pass sustained conversation acceptance.

`live3` adds a temporary USB graphics-freeze diagnostic. The user reported continued stutter with graphics frozen; animation was restored. This rules out animation as the sole cause, not every possible CPU/cache interaction. Device-to-gateway TCP retransmissions, send timeouts and bounded upload queue overflow were also observed. No I2S read/write error was recorded in those samples.

A separate synthetic test ran from the actual server service user through its proxy, without ESP32 in the path:

| Exit tested once | Native audio chunks | Largest arrival gap | p95 arrival gap | Gaps >900 ms | Result |
|---|---:|---:|---:|---:|---|
| Japan exit | 610 | 1167 ms | 481 ms | 6 | Completed, no API error |
| US exit | 634 | 940 ms | 442 ms | 2 | Completed, no API error |
| Taiwan exit | 0 | — | — | — | ECONNRESET before session ready |

These are arrival gaps in a continuous stream, including silent frames. They are **not** measured audible dropouts. Prompt content was held constant but model output varied, so a single comparison cannot prove long-term exit superiority or separate provider scheduling from proxy buffering. The US exit was selected provisionally for further device testing.

Synchronized server/device observations subsequently showed native chunks arriving while the device TCP connection accumulated unsent data and disconnected. Upstream variation and downstream transport faults therefore both remain under investigation; this record does not blame all failures on the household network or all failures on the proxy.

A further Mac control test connected through the same public gateway with synthetic input: 506 audio chunks, two counting requests, one connection and no reported errors; the largest arrival gap was 1060 ms. This does not establish physical speaker quality. A subsequent firmware experiment increases TCP send/receive buffers to 23040 bytes, sizes the receive mailbox to 18 entries (window/MSS + 2), bounds out-of-order buffers at 8 and enables SACK. The build and app digest verification passed. In the first physical interval, five transport failures still occurred before a later approximately one-minute connection completed idle shutdown. No OOM was seen (sampled free internal memory remained above 40 KiB). It has not passed sustained audio acceptance.

The user subsequently tested `live4` at 0 dB and reported: “音量合适，连续回答顺畅” (suitable volume, smooth continuous replies). This is a successful physical short check, not a 30-minute conversation or a conclusive attribution of improvement to a single network setting. Earlier failures above remain part of the record.

## Still required

- Thirty minutes of continuous real-device conversation with stable playback and graphics.
- Natural interruption/AEC, explicit stop latency, reconnect and old-audio rejection on hardware.
- Adult/child listening and family-background scenes, without recording household audio.
- Full automatic memory, correction/deletion, summary non-reintroduction and restart regression under Terra.
- Device idle/long-story/farewell behavior and failure recovery with actual playback telemetry.
- Usage/time reconciliation, pending-task recovery and prolonged operation.

中文摘要：双模型、工具及部分记忆链路已有真实 API 结果；软件通过不等于实机通过。问候曾恢复顺畅，但后续对话仍卡，冻结眼睛未解决。三出口首轮对照后暂选美国出口；服务器上游到达间隔与设备 TCP 积压均有证据，尚未完成根因闭环。音量按后续要求已保存为 0 dB；随后用户确认新版本短测音量合适、连续回答顺畅。30 分钟实机、自然插话、完整记忆和稳定性仍待验收。
