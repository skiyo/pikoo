# Contributing

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

Start with [Quick Start](docs/getting-started.md) and [Development](docs/development.md). Open a focused issue/PR describing the user-visible change, implementation and checks. Use English or Chinese.

Run `bash tools/check.sh` for code changes. Keep Provider, corpus, audio and USB tests explicit and isolated; do not invoke paid APIs or household capture from ordinary checks. Test firmware changes on the exact non-touch board before claiming physical acceptance.

Retain dependency versions and license headers. Do not submit API keys, device tokens, NVS, family profiles, source recordings or private evaluation logs. Add documentation in both languages for public behavior changes. Original contributions are submitted under Apache-2.0; model/data submissions require separate documented source terms.
