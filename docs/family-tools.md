# Family tools

**English** | [简体中文](family-tools.zh-CN.md)

DeepSeek Search uses the configured `DEEPSEEK_API_KEY`, validates a 1–128 character query, requests 5 results by default (maximum 8) and applies an 8-second deadline without retry loops. Search results include title, URL, snippet and available publication time. Auth, credit and rate errors are reported as failures.

Public-page reading uses the existing safe fetcher: internal destinations are blocked, redirects revalidated, size bounded to 1 MiB / 12,000 text characters and total time to 8 seconds. Retrieved pages are data, not instructions to override the Agent.

Family notes support explicit add/query/update/delete/clear operations and persist by owner, separately from inferred memory. Ambiguous changes need clarification. Existing tools are selected by Terra through the Gateway runtime. New MCP integrations are possible extension work; no calendar, map or smart-home integration is implied.

Tool IDs are durably reserved to reduce replay. A crash after a reservation can leave an uncertain result requiring inspection, rather than blindly repeating a side effect. Different IDs for the same request are not guaranteed exactly-once.
