# Hi Pikoo model card

**English** | [简体中文](MODEL_CARD.zh-CN.md)

## Intended use

Full **Hi + piku / piko** local wake word for an ESP32-S3 household pet. Incidental complete “Hi Tikoo/Tiko” triggers are tolerated, with no recall promise. Hi alone, the name alone, incomplete phrases and ordinary speech are not intended wake phrases.

## Runtime contract

| Property | Value |
|---|---|
| Version | 1.0.0 |
| Artifact | hi_pikoo.tflite |
| Size | 98,064 bytes |
| SHA-256 | `5efc03a7bbe992eb66ccefb1e1d14a81e071fceb45df3c2d6c2caa3df251ca50` |
| Audio / frontend | 16 kHz mono PCM16, 40 microfrontend bins, 30 ms window / 10 ms step |
| Model I/O | Stateful INT8 `[1,3,40]` input, scalar UINT8 probability |
| Decision | Every 30 ms; average last 3 probabilities ≥ 0.90 |
| Policy | [wake-policy.json](wake-policy.json), bound to model hash and frontend fingerprint |

The checkpoint uses the independent causal model in `training/hi_pikoo_model.py`; the export uses microWakeWord streaming/conversion layers. Read the accompanying checkpoint configuration in the release before reconstructing the network. A training checkpoint is not a portable inference runtime.

## Evidence and limits

Pinned native Micro and host feature/probability checks matched on the selected engineering fixtures. A device benchmark of 600 iterations measured inference p99 10.414 ms, maximum 10.437 ms and arena 48,796 bytes. This does not measure every full-pipeline scheduling condition.

Formal family acceptance, independent real-child recall, 8-hour mixed background false-wake and 72-hour endurance are incomplete. Synthetic/development results do not establish those outcomes. This release publishes the currently used model; version 1.0.0 is not a claim that all accuracy targets passed.

## Download and terms

[Download the model package](https://github.com/skiyo/pikoo/releases/download/v1.0.0/hi-pikoo-model-1.0.0.zip). It includes inference weights, checkpoint, policy and checksums. Read [model terms](LICENSE.md) and [source attribution](ATTRIBUTION.md). Raw datasets, family audio and private manifests are excluded. Original source code remains Apache-2.0; model terms are separate.
