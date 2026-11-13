# Development

**English** | [简体中文](development.zh-CN.md)

## Layout and extension

`pikoo_config` validates versioned settings and complete endpoints. `LiveAgent` implements the selected voice protocol and classified context. `BackendAgent` owns bounded model/tool loops; provider adapters normalize Responses, Chat Completions and search results. `HttpResponse` incrementally decodes bounded HTTP. The ESP network worker uses verified TLS, optionally through HTTPS CONNECT, and returns tagged results to the session task. NVS and board APIs stay outside the shared core.

Add protocols explicitly rather than guessing from domains. Add tool schemas and executors together. Keep audio deadlines independent of networking, and invalidate cancelled task tokens before handling results. Do not log headers, raw API bodies, configuration or family snapshots.

## Silent checks

Activate ESP-IDF so `IDF_PATH` locates cJSON. The host needs C++17, OpenSSL development libraries and Python; on macOS set `OPENSSL_PREFIX` to the Homebrew OpenSSL prefix.

```sh
PIKOO_SANITIZE=1 tools/test-local-agent.sh --services
tools/test-local-agent.sh --network --cycles 100
tools/test-local-agent.sh 28800
(cd firmware/simulator && npm ci --ignore-scripts)
bash tools/check.sh
```

Tests use synthetic PCM and in-memory sinks. They never open an audio device. The graphical eye preview is separate from the native Agent simulator. Rebuild the ESP firmware and report image/static memory separately from desktop CPU/RSS. Board TLS concurrency, AEC and acoustic behavior require board evidence; see [verification](release.md).

Optional Python training tests require the separate training environment. Run `PIKOO_CHECK_TRAINING=1 bash tools/check.sh` after installing its requirements. Runtime checks do not require TensorFlow.
