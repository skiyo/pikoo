# Frequently asked questions

**English** | [简体中文](faq.zh-CN.md)

## Product and hardware

### Is the whole AI model running on ESP32?
No. ESP32 runs wake detection, conversation state, orchestration, tools and storage. Voice and reasoning models run at your configured endpoints. This is a device-owned Agent with cloud inference.

### Does Pikoo work without Internet?
Local wake, displays, buttons and stored data remain local capabilities. Voice conversation, reasoning and online search need reachable services. There is no offline conversational fallback.

### Do I need a separate Pikoo server?
No application server is required. Configure the voice and reasoning providers directly. Optional standard transport configuration is described in the configuration reference.

### Can I use any ESP32 board?
The packaged images target the non-touch Waveshare DualEye board with 16 MiB Flash and 8 MiB PSRAM. Another board requires porting pins, displays, codecs, memory and partitions, followed by a new build and hardware validation.

### Is an enclosure required? Can I use a different printer?
The electronics can be configured outside an enclosure. Printable parts and an offline illustrated guide are included. A different printer/material requires fit validation; printer profiles and a successful STL import do not prove mechanical fit.

## Setup and services

### Which download should I choose?
Use the firmware ZIP for installation. Use the model ZIP for inference weights/checkpoint and model metadata. GitHub's automatic source ZIP contains tracked source and weights but does not contain generated board images. The app BIN is a single application partition image.

### Where are the model files? Is Git LFS needed?
They are tracked under `models/hi-pikoo/`: `hi_pikoo.tflite` and `checkpoint.weights.h5`. Git LFS is not required. The checkpoint is for training; firmware uses the TFLite model with its matching policy.

### Can I use a chat-only provider for voice?
Not with the Live adapter. It requires client delegation, transcript events, PCM and Decisions. A compatible HTTP chat endpoint is sufficient only for the reasoning role when it implements function calling and tool-result messages.

### Can all services have different keys and providers?
Yes. Each service has its own endpoint, protocol, key and model fields. Credentials are not inherited across services. Changing a URL does not convert one protocol into another.

### Does passing configuration validation prove API access?
No. Validation is local. The provider must separately accept the model/key, implement the required protocol and be reachable from the board. A 401 usually concerns authentication; 429 concerns provider limits or quota.

### Is search mandatory? Can Pikoo read arbitrary URLs?
Search defaults to off. Tavily search may additionally enable `read_webpage` through a same-origin extraction URL. Responses search exposes search results and citations, not arbitrary webpage extraction. Redirecting or authenticated pages are not guaranteed to work.

### How do I change English to Chinese?
Set `agent.language` to `zh-CN` and run `device.py configure`. The wake phrase stays “Hi, Pikoo”. `configure.py --language zh-CN` changes setup prompts; the configuration's language controls the device.

### Must I recompile when a key expires or Wi-Fi changes?
No. Update the complete private JSON and provision it over USB. Configuration is replaceable ordinary NVS. No eFuse operation is involved in normal setup or key rotation.

## Privacy, memory and controls

### Why does the screen say MIC OFF after a USB operation?
The transfer utility deliberately mutes the device before maintenance. Export leaves it muted. Run `device.py diagnose --port PORT --command unmute` when ready; do not reflash just to remove MIC OFF.

### Does idle audio leave the device?
Idle wake detection is local. Active conversation sends audio and task context to configured services. Mute disables capture and closes the active session. See the security guide for provider and physical-access boundaries.

### Are keys encrypted? Is a family export safe to publish?
The default configuration uses ordinary NVS without secure boot or Flash encryption. Physical Flash access may expose keys. A family export excludes credentials but includes list/memory/context content, so it is still private data.

### Does Pikoo learn everything it hears?
Automatic long-term memory learning is off. Explicit memory instructions control saved facts. Recent conversation is bounded context and differs from long-term memory. Pikoo does not infer separate speaker identities.

### How much can it save?
Shopping, todo and memory each allow 32 entries, up to 512 UTF-8 bytes each. Context has at most 12 fragments; the complete snapshot is bounded to 24 KiB. UTF-8 byte length is not character count.

### Why was a repeated action not applied twice—or why did it repeat?
Persisted call IDs prevent duplicate execution within the retained receipt window. Two separately generated requests can have different IDs even if their text is similar. Read back data before retrying after uncertain network outcomes.

### Does ending a conversation erase lists?
No. End clears short-term context, while lists and explicit memories remain stored. `forget` removes service configuration, not family data. Import replaces a snapshot; export first when retaining current data matters.

## Reliability, development and terms

### Does an eight-hour simulation prove eight-hour board stability?
No. Accelerated PCM replay checks software behavior under synthetic load. Board heap, Wi-Fi, I²S, AEC, power and thermal behavior need hardware measurements. Verification documents state the scope of each result.

### Can I test without microphones or sound?
Yes. Native tests use synthetic PCM and memory sinks. The offline eye preview renders states without provider calls or audio devices. See the development guide.

### Can the firmware package be used commercially?
Original source uses Apache-2.0. Wake weights and firmware containing them retain separate non-commercial model terms and third-party restrictions. Source licensing alone does not grant commercial model rights; consult the included terms for the intended distribution.

### How do I report a problem usefully?
Include firmware/version, board type, OS, operation, expected/actual behavior and redacted status/error codes. State whether it is a simulator or board result. Exclude configuration files, keys, recordings and family snapshots. Use private vulnerability reporting for security issues.

[Quick start](getting-started.md) · [Troubleshooting](troubleshooting.md) · [Security](../SECURITY.md)
