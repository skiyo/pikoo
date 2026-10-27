# Pikoo documentation

**English** | [简体中文](README.zh-CN.md) · [Project](../README.md) · [Website](https://pikoo.lol/)

Choose a guide for the task at hand. The project README introduces Pikoo as a family realtime voice AI Agent; these guides explain how to run, change and verify it.

## Enclosure printing resources

The three original cat-enclosure STLs, print order, illustrated assembly guide and checklist are in the [enclosure directory](../hardware/enclosure/README.md). The project family reports successful printing, assembly and home use (2026-10-27); that hardware feedback is separate from this module’s software/research checks.

## Start and build

| Goal | Read |
|---|---|
| Try the desktop eyes, then optionally connect a live server | [Getting started](getting-started.md) |
| Select the board, speaker and audio hardware | [Hardware](hardware.md) |
| Build, provision, diagnose or recover the DualEye device | [Firmware and USB](firmware.md) |
| Understand device, server, model and training boundaries | [Architecture](architecture.md) |
| Find environments, checks and contribution entry points | [Development](development.md) |
| Configure the Agent runtime and operate a private gateway | [Server](../server/README.md) |
| Develop an authorized local wake model | [Training](../training/README.md) |

## Work on a specific behavior

| Topic | Guide |
|---|---|
| Eye rendering and expressions | [Dual-eye renderer](dualeye.md) |
| Wake, sleep, explicit end and reconnect | [Conversation lifecycle](conversation-lifecycle.md) |
| Current context, family memory, recall, time and output language | [Context and memory](context-memory.md) |
| Search, web reading and family lists | [Family tools](family-tools.md) |
| Opt-in selective responses and silence handling | [Quiet companion mode](companion.md) |
| Device-facing audio and events | [GCP 7 protocol](gcp7.md) |

## Check the evidence

Read the [validation summary](validation-summary.md) before treating any software result as physical acceptance. [Device validation](device-validation.md), [DualEye validation](dualeye-validation.md) and [open-source publication checks](open-source-validation.md) record dated observations.

Wake-word research is split into [pronunciation coverage](wake-pronunciations.md), [continuous-speech context](wake-context.md), [capacity measurements](wake-capacity.md) and the [preserved training notes](../training/research-notes.zh-CN.md). Old results keep their original dates and limitations.

Core guides have Chinese counterparts. Some historical engineering/host records remain in Chinese; the English summaries identify their scope rather than turning an old result into a current pass.

For contribution, security and reuse rules, see [Contributing](../CONTRIBUTING.md), [Security](../SECURITY.md) and [Third-party attribution](../THIRD_PARTY.md).
