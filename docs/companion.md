# Selective replies

**English** | [简体中文](companion.zh-CN.md)

Pikoo uses the voice model's selective response behavior with quiet conversational instructions. It may listen without replying and should avoid talking over family-to-family conversation. The current policy does not require the name in every turn. Silence markers must not be spoken or saved as meaningful conversation.

This is not deterministic addressee recognition. The separate Terra classifier controls effective idle and what may enter automatic memory; it does not block each voice packet or guarantee zero unsolicited replies. Keep local mute and idle sleep available. Do not present always-listening mode as a privacy-free local-only operation: active dialogue audio reaches the provider.
