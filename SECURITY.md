# Security

**English** | [简体中文](SECURITY.zh-CN.md)

Report sensitive vulnerabilities through [GitHub private vulnerability reporting](https://github.com/skiyo/pikoo/security/advisories/new), not a public issue containing an exploit against a household deployment or credentials. Include affected version, impact and a minimal sanitized reproduction.

Never publish provider keys, pairing fragments, device tokens, NVS backups, family memory or source recordings. Rotate exposed credentials at their provider. Use trusted HTTPS/WSS, per-device revocable credentials, fixed allowed origins and local-only admin/proxy endpoints.

The development firmware does not enable secure boot or Flash/NVS encryption. Physical access can expose device credentials. Standby wake audio stays local; local mode establishes end-to-end OpenAI TLS inside a Mihomo tunnel. Provider credentials are sent only inside that TLS connection, stored in ordinary NVS and replaceable/removable over USB. The legacy Gateway mode remains separate. The marketing site's local eye animation does not access a microphone.
