# Development and testing

**English** | [简体中文](development.zh-CN.md)

## Set up the right environment

Firmware builds require ESP-IDF 5.5.5 and the target ESP32-S3 toolchain. Host tests require a C++17 compiler, Python, OpenSSL development headers/libraries and Node.js 24+. Activate IDF so `IDF_PATH` exposes cJSON. The simulator has its own locked npm dependencies:

```sh
(cd firmware/simulator && npm ci --ignore-scripts)
```

On macOS, install OpenSSL and set `OPENSSL_PREFIX` to its installation prefix when needed. Linux needs the OpenSSL development package. Training dependencies are separate; normal runtime development does not require TensorFlow or a service key.

## Repository map

| Directory | Change here when… |
|---|---|
| `firmware/components/pikoo_core` | Adding configuration, protocol normalization, session/tool behavior |
| `firmware/main` | Changing ESP TLS, NVS, audio, wake or board drivers |
| `firmware/simulator` | Improving native test drivers or offline eye preview |
| `tools` | Changing installation, provisioning, packaging or checks |
| `examples` | Maintaining placeholder-only public configuration |
| `models/hi-pikoo` | Updating a reviewed model/policy and its metadata |
| `training` | Working on corpus validation, training or model evaluation |
| `hardware/enclosure` | Editing printable parts and bilingual assembly instructions |

## Run silent software checks

```sh
bash tools/check.sh
PIKOO_SANITIZE=1 bash tools/test-local-agent.sh --services
bash tools/test-local-agent.sh --network --cycles 100
bash tools/test-local-agent.sh 28800
```

`check.sh` covers publication/link checks, native audio/session/eyes, preview/guide tests, generation planners, sanitized service tests and Python tooling. The explicit service command is useful during focused development; it need not be repeated after an unchanged passing full suite. Network fixtures use fake credentials and local TLS services. The last command accelerates 28,800 seconds of synthetic PCM; it is not eight hours of real elapsed-time board operation. These tests do not open microphones or speakers.

To preview eyes, run `bash tools/start-dualeye.sh` and open `http://127.0.0.1:8793/dualeye`. Stop with Ctrl+C or `bash tools/stop-dualeye.sh`. Preview poses exercise rendering, not live provider behavior.

## Extend an adapter or tool

1. Define the protocol or tool contract, required fields, limits and error behavior.
2. Add explicit protocol validation in the shared configuration layer and Python setup validator.
3. Normalize provider responses in the adapter; do not put provider-specific parsing into storage or audio code.
4. Register tool schema and executor together. Check all arguments before mutation.
5. Preserve task cancellation, bounded rounds/results and call-ID deduplication.
6. Test success, malformed data, fragmented HTTP, authentication/rate failures, cancellation and late results. Test persistence recovery for writes.
7. Update example configuration and both language versions of the docs.

Do not infer protocols from domains or log raw provider bodies, headers, configuration or snapshots. Retrieved text must remain data. Keep network work off realtime audio tasks.

## Validate firmware changes

Build with `tools/build-device.sh` and record image size, partition fit and static memory. On the board measure heap low water, largest free block, stack margin, queue peaks and I²S errors under concurrent voice/backend work. Test restart readback and cancellation with disposable data. Acoustic tests, power-cut tests and long-duration runs require explicit hardware evidence; report duration and workload, not only “passed”.

Training Python tests are opt-in: install `training/requirements.txt` in a separate environment and use `PIKOO_CHECK_TRAINING=1 bash tools/check.sh`. Provider generation and corpus collection are explicit activities, never side effects of ordinary checks.

[Architecture](architecture.md) · [Release process](release.md) · [Contributing](../CONTRIBUTING.md)
