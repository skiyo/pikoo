# Pikoo documentation

**English** | [简体中文](README.zh-CN.md)

Choose a route rather than reading every page in order.

- **First device:** Quick start → User guide → FAQ. Consult configuration while filling the private JSON.
- **Maintain a device:** Firmware and USB → Troubleshooting → Context and memory.
- **Develop or extend:** Architecture → Tools → Development → Verification and publishing.
- **Build the enclosure or train a model:** use the specialist guides linked below.

## Documentation map

| Guide | What it covers |
|---|---|
| [Quick start](getting-started.md) | Download, configure, back up, install and make the first call |
| [User guide](usage.md) | Wake, buttons, voice examples, volume and language |
| [Configuration reference](configuration.md) | Every field, limit, service role and protocol requirement |
| [FAQ](faq.md) | Hardware, services, privacy, models and reliability |
| [Troubleshooting](troubleshooting.md) | Symptoms, diagnostics and recovery decisions |
| [Hardware](hardware.md) | Board target, pins, assembly and electrical checks |
| [Firmware and USB](firmware.md) | Build, update, configure, export/import and restore |
| [Capabilities](agent.md) | Supported tasks and acceptance examples |
| [Architecture](architecture.md) | Ownership, adapters, scheduling, cancellation and storage |
| [Tools](family-tools.md) | Local mutations, confirmation, search and errors |
| [Context and memory](context-memory.md) | Capacity, lifetime, receipts and backup boundaries |
| [Conversation lifecycle](conversation-lifecycle.md) | States, interruption, farewell, mute and reconnect |
| [Dual eyes](dualeye.md) | Shared rendering, offline preview and panel validation |
| [Development](development.md) | Environment, repository map, tests and extensions |
| [Verification and publishing](release.md) | Evidence scope, packaging, checksums and release process |
| [Public repository quality](public-audit.md) | Publication checks, privacy and license boundaries |

## Specialist material

[Enclosure and printing](../hardware/enclosure/README.md) · [Wake model](../models/hi-pikoo/README.md) · [Training](../training/README.md) · [Security](../SECURITY.md) · [Contributing](../CONTRIBUTING.md)

English is the default product/documentation language; each guide links to its Chinese counterpart. Commands use placeholders such as `PORT` and `/absolute/private/device.json`; replace them locally. Run commands from the repository/package root unless specified otherwise. A documented feature means implemented support, not compatibility with every provider or board.
