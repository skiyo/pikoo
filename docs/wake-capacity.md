# Larger wake-network development

[English](wake-capacity.md) | [简体中文](wake-capacity.zh-CN.md)

On 2026-10-18 the user authorized larger networks and continued iteration toward adult, child and mixed-name wake acceptance. **64 KiB was an initial project budget.** DualEye experiments now explicitly allow up to **512 KiB of model Flash**, retaining the 256 KiB arena allocation, 30 ms inference interval and unchanged accuracy gate. The 6 MiB application partition is unchanged; weights remain embedded and private. Historical 1.83-inch builds retain 64 KiB.

## Observed progress

| Candidate | Channels / first layer | INT8 bytes | Streaming target hits | False wakes |
|---|---|---:|---:|---:|
| V11A, widened from V10H | 96 / 64 | 134,320 | 286/316 | 6/730 |
| V11B, fresh training, epoch 13 | 128 / 64 | 189,936 | 304/316 | 3/730 |
| V11B, epoch 14 | 128 / 64 | 189,936 | 293/316 | 1/730 |
| V11C, added train contrasts, epoch 1 | 160 / 80 | 261,312 | 291/316 | 0/730 |
| V11D, frozen encoder + residual readout, epoch 7 | 128 / 64 + 64-unit readout | 201,096 | 285/316 | 1/730 |
| V11G, short ordered branch, epoch 1 | 128 / 64 + 24-channel branch | 250,688 | 312/316 | 5/730 |

V11B epoch 13 detects all 38 newly added original fictional targets, including both pronunciations and adult/childlike styles. Epoch 14 passes the recall groups but falsely wakes on one pitch-shifted “你好皮球”. All 18 B epochs were checked; none passed the entire gate. These are reused **development** recordings, not blind or human acceptance. No household recording was used for training, tuning, selection or scoring this round.

Synthetic-only device measurements with both displays running:

| Model | Device arena | Frontend + inference P99 | Maximum | Deadline misses / errors |
|---|---:|---:|---:|---|
| V11A | 42,028 B | 11,410 µs | 11,427 µs | 0/600 / 0 |
| V11B epoch 13 | 53,228 B | 15,516 µs | 15,641 µs | 0/600 / 0 |
| V11C epoch 1 | 70,732 B | 20,556 µs | 20,643 µs | 0/600 / 0 |
| V11G epoch 1 | 61,260 B | 19,923 µs | 20,043 µs | 0/600 / 0 |

The timing image disables the microphone, amplifier and network. It feeds deterministic generated PCM at a 30 ms cadence and renders eyes concurrently. Each temporary test restored the V8D application and verified its SHA-256, without writing NVS. This establishes preliminary computational headroom; real audio/AFE/network concurrency and physical wake trials remain separate.

C retains all **1,046** F validation waveforms and labels. Its training set has 1,058 targets and 9,007 non-targets after screening/curation, including 118 new TRAIN-mined prefixes and fresh training-condition near-phrase synthesis. Derivatives keep parent splits. Mining scored no validation/test speech. New synthetic test audio was separately generated and content-screened before scoring; frozen test hashes and the eight household waveform hashes are excluded from training and calibration. Fictional childlike synthesis is not real child target speech.


C eliminates false wakes at its first checkpoint but regresses legacy targets and one adult mixed-name group. All six C checkpoints and seven D readout checkpoints failed the unchanged gate. C also misses the 20 ms P99 development target and reaches only 7.4 fps under this synthetic display load. A larger file alone is not acceptance.

Ongoing ablations retain the same development waveforms and protected test hashes: E reduces the negative-loss multiplier; F additionally freezes pretrained batch-normalization statistics while fine-tuning convolutions; G adds a short ordered acoustic branch to the frozen whole-phrase encoder. The G branch shares the first causal features, learns three depthwise stages (5/9/13, 24 channels), retains 20 time steps and uses a zero-initialized residual logit. Its initial function and subsequent offline/streaming alignment are tested. It is not a pretrained phoneme recognizer.

A separate 4.5-second startup-context diagnostic at simulated background RMS 0/20/80 did **not** resolve B's regression. Historical one-second cold-start scores and labels remain the gate. Diagnostic input contexts are explicit in reports; the gate rejects a mismatched context. No warm-up guard or threshold relaxation was deployed.


G's first export was rejected because one recurrent buffer stayed FLOAT32. The repair inserts an exact unit depthwise kernel only at export, copies every existing layer weight, verifies unchanged probabilities and checks the entire TFLite graph for integer compatibility. Six reference/Micro cases with three resets each then passed (host arena 61,808 bytes). On-device synthetic timing used 61,260 bytes and reached 7.4 fps; this is still below the animation design target.

Later experiments preserve all failed results: I adds training-only dropout (`--dropout .15`) and a longer window-loss patience; K/L interpolate compatible checkpoints into one network, with optional TRAIN-only normalization calibration. These do not run two networks on the device. M (`--temporal-readout --head-backbone-weights ...`) keeps the frozen encoder and replaces the final average with an ordered head. Its initialization tiles the original classifier weights across time and divides by the number of steps, preserving the original function. It trains only the new classifier and uses an integer identity consumer for its recurrent state. No new model download, family training, threshold relaxation or blind-test selection was involved.

## Reproducing the checks

Use an authorized local corpus and pinned training environment. Pass `--max-model-bytes 524288` explicitly when training or checking a larger model. `--save-epoch-checkpoints` retains private checkpoints; `--export-only --resume-weights /private/epoch.weights.h5` exports a specific one without further fitting. The same manifest, preprocessing, protected hashes and architecture are required. Score full streaming audio, then apply [the fixed policy](../training/policies/dualeye-v11-development.json) with `training/streaming_gate.py`; that policy requires the exact historical development corpus. A zero-false-wake software pass does not establish an eight-hour background rate.

For temporary device timing, build in a **separate directory** so the normal restore image is preserved:

```sh
cd firmware
idf.py -B build-wake-benchmark \
  -DSDKCONFIG="$PWD/build-wake-benchmark/sdkconfig" \
  -DPIKOO_WAKE_MODEL=/private/authorized-model.tflite \
  -DPIKOO_WAKE_MAX_BYTES=524288 -DPIKOO_WAKE_BENCHMARK=ON build
```

Before flashing, protect a verified copy of the current application and its build metadata, check the actual partition layout and use the existing app-only upgrade tool. Restore and verify that application after recording the result, including on failure. Do not overwrite configuration or publish restricted binaries. `tools/build-device.sh` explicitly turns benchmark mode OFF for normal builds. The benchmark yields on overruns to avoid starving diagnostics/graphics and reports failures rather than relaxing the deadline.
