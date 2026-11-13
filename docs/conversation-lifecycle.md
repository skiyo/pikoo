# Conversation lifecycle

**English** | [简体中文](conversation-lifecycle.zh-CN.md)

Idle audio stays on-device for wake detection. A wake opens the configured Live service; readiness enables upload and a brief greeting. The microphone and playback run independently of backend HTTP work.

Interruption clears queued playback and cancels backend work. Transcript classification requires a complete stop/correction phrase, so a constraint such as “do not modify” must not cancel a read query. Late task tokens are discarded. Farewell waits for audible playback to drain, then closes the voice connection; ordinary inactivity closes it after 60 seconds. Explicit End clears short-term context, while idle sleep retains it.

Mute closes the session, clears playback and disables capture. Missing configuration never falls back to a different runtime. Authentication errors require fixing the corresponding service configuration; rate limits use backoff rather than repeated rapid retries.
