# Context and memory

**English** | [简体中文](context-memory.zh-CN.md)

Recent text history resumes the topic after reconnect or sleep. A logical conversation identifier is stored on the device for up to 24 hours; the Gateway restores bounded text and topic summaries when a new model transport starts. Audio and hidden model state are not restored.

Long-term family memory is separate Markdown storage. It learns suitable facts from explicitly directed interaction without requiring “remember this” each time. Terra prepares summaries and memory updates through the durable learning queue. Background conversation and unknown-address segments are excluded. Failures remain pending/visible rather than silently switching providers.

Corrections and deletion operate on the stored memory and invalidate obsolete summaries. Notes/lists are a separate explicit tool store, not inferred facts. Use the same family owner for shared household access, and ask who is speaking when needed rather than inferring voice identity. Current time is injected by the server in Asia/Shanghai.

Back up all private state together. Physical household recall and long-session memory quality remain workload-dependent; successful storage tests are not a blanket claim of perfect memory.
