# Context and memory

**English** | [简体中文](context-memory.zh-CN.md)

Shopping lists, todos, explicit memory and recent conversation are separate data sets. Each list/memory group has at most 32 entries, each up to 512 UTF-8 bytes. Context stores at most 12 text fragments. A snapshot including write receipts is at most 24 KiB.

Only explicit user instructions should change long-term memory; automatic learning is off. Corrections/deletions clear stale conversation context. Two-slot NVS commits preserve the preceding snapshot if a commit fails. USB export/import moves family state without service credentials. Ending a session clears short-term context; ordinary idle sleep retains it.

[Tools](family-tools.md) · [USB](firmware.md)
