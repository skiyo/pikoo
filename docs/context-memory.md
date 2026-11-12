# Context and memory

**English** | [简体中文](context-memory.zh-CN.md)

Local mode stores family data in device NVS. Reconnect and sleep restore up to 12 recent text entries, never old audio or hidden model state. Transcript fragments are grouped by their timeline. Unclassified/background input is excluded from saved context.

Shopping, to-do and explicit memory are separate groups, each capped at 32 entries of 512 UTF-8 bytes. Automatic learning is disabled. Corrections/deletion change durable data and clear outdated context. The latest 32 tool receipt IDs are committed with state to prevent duplicate writes on retry.

Snapshots are limited to 24 KiB and use two commit slots. USB export/import transfers family data without credentials. Keep original migration backups and resolve conflicting historical memories before importing them. The shared device does not infer speaker identity.

Server-side Markdown, summaries and learning queues remain available only in compatibility GCP 7 mode. See [USB commands and data format](local-agent.zh-CN.md).
