# Context and memory

**English** | [简体中文](context-memory.zh-CN.md)

Shopping lists, todos, explicit memory and recent conversation are separate data sets. Each list/memory group has at most 32 entries, each up to 512 UTF-8 bytes. Context stores at most 12 text fragments. A snapshot including write receipts is at most 24 KiB.

Only explicit user instructions should change long-term memory; automatic learning is off. Corrections/deletions clear stale conversation context. Two-slot NVS commits preserve the preceding snapshot if a commit fails. USB export/import moves family state without service credentials. Ending a session clears short-term context; ordinary idle sleep retains it.

[Tools](family-tools.md) · [USB](firmware.md)

## Distinguish the stores

| Data | Written by | Lifetime |
|---|---|---|
| Shopping/todo | Explicit tool actions | Persistent until changed or replaced |
| Explicit memory | Requested memory tool actions | Persistent until corrected/deleted |
| Conversation context | Bounded interaction handling | Cleared by explicit End/corrections as applicable |
| Write receipts | Successful mutations | Finite deduplication window |
| Service configuration | USB provisioning | Replaced independently of family snapshots |

The complete snapshot shares one size budget, so filling every individual collection limit is not a promise that all maximum-size entries will fit simultaneously. Capacity errors must be reported without pretending a write succeeded.

## Durable does not mean unlimited recovery

Two slots protect against an incomplete software commit; they are not a replacement for a private backup or a guarantee against all Flash/power faults. Export before importing or destructive clear operations. A full-Flash backup contains credentials as well as data; a family export excludes credentials but remains private. Import replaces rather than merges. See [USB maintenance](firmware.md) for commands and reboot requirements.

Only one shared device store is provided. There is no per-speaker access control, automatic synchronization, conflict resolution across devices or automatic learning from ambient conversation.
