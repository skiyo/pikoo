# Conversation lifecycle

**English** | [简体中文](conversation-lifecycle.zh-CN.md)

Idle audio stays on-device for wake detection. A wake opens the configured Live service; readiness enables upload and a brief greeting. The microphone and playback run independently of backend HTTP work.

Interruption clears queued playback and cancels backend work. Transcript classification requires a complete stop/correction phrase, so a constraint such as “do not modify” must not cancel a read query. Late task tokens are discarded. Farewell waits for audible playback to drain, then closes the voice connection; ordinary inactivity closes it after 60 seconds. Explicit End clears short-term context, while idle sleep retains it.

Mute closes the session, clears playback and disables capture. Missing configuration never falls back to a different runtime. Authentication errors require fixing the corresponding service configuration; rate limits use backoff rather than repeated rapid retries.

Farewell cancels backend work immediately while allowing the goodbye playback to drain. A clearly addressed new question cancels the farewell timer and resumes normal interaction.

## Observable states

## State guide

| State | Audio/network behavior | User action |
|---|---|---|
| Unconfigured | No voice session | Provision over USB |
| Idle | Local wake; no idle upload | Say the full phrase or press BOOT |
| Connecting | TLS/session setup; wait for readiness | Wait for greeting or inspect a failure |
| Active | Capture/upload and playback follow session events | Ask, follow up, interrupt |
| Farewell | Backend cancelled; goodbye drains | Wait, or address a new question |
| Muted | Capture/upload disabled; queue cleared | Hold BOOT or send `unmute` |

Cancellation has two parts: invalidate backend result tokens and change playback generation. This prevents an old network response or queued audio from reappearing in a new turn. It does not undo a mutation already committed before cancellation.

## Reconnection and errors

A recoverable disconnect can re-establish the configured session; old playback must not resume. Permanent credential/configuration errors require configuration repair. A brief successful connection is not proof of uninterrupted playback. Use redacted status counters for repeated failures and test both cancellation-before-write and disconnect-after-write separately.

[Controls](usage.md) · [Architecture](architecture.md) · [Troubleshooting](troubleshooting.md)
