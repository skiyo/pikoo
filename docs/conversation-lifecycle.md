# Session lifecycle

**English** | [简体中文](conversation-lifecycle.zh-CN.md)

Standby closes the eyes and keeps wake processing local. Wake connects/authenticates the Gateway and Live; readiness opens the eyes and submits the greeting as the first turn. CONNECTING is not a ready state. Authentication, quota or provider failures must remain visible.

During conversation, the device continuously uploads microphone audio unless muted. Stop immediately clears playback without sleeping. Generation changes reject late audio. Disconnect clears all queued sound and uses bounded backoff; reconnect preserves the logical topic where valid.

Native Live semantic idle uses the 60-second/15-second rules in [Live](openai-live.md). Explicit contextual farewell drains its answer then sleeps. Standby uploads no ambient sound. A new wake creates a fresh voice transport with saved text context. Device end/reset/identifier expiration and server text history are distinct state boundaries.
