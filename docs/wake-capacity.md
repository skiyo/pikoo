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

## Local command-confirmation prototype

An optional MN7 Chinese verifier from the already installed ESP-SR package is being tested **only in a separate offline diagnostic image**. Its acoustic+FST pack is 2,681,351 bytes; it has separate ESPRESSIF-product license terms. No new model was downloaded and no verifier weights or audio enter this source tree. The normal build explicitly disables both diagnostic modes.

The first functional TRAIN-only probe detected 2/4 synthetic targets and rejected all eight non-targets (four near phrases and four authorized real-child ordinary-speech clips). Both Mandarin targets were missed, so this is **not a qualifying candidate**. Mean processing was 15,472 µs per 512-sample frame; 5,321,528 bytes of PSRAM remained with the microphone/network disabled. The all-PSRAM TRAIN-only diagnostic has now run: the two missed Mandarin targets decoded as the correct command with probabilities 0.620994 and 0.685212, still below the unchanged 0.7 probe cutoff. The two mixed-name examples scored 0.823276 and 0.972275. This does not qualify a release. See the [actual probe record](../training/reports/command-confirmation-probe.json).

The first startup failure identified a missing FST dictionary. `tools/check_command_models.py` now checks the acoustic files, required dictionary, header bounds and payload offsets before CMake builds this image. Failed and successful probes restored and read-verified the protected application. The user reconnected USB, fresh idle status recovered, and probe3 was restored with readback verification. A 128-case TRAIN batch is now being exercised over checksummed, bounded USB frames; an interrupted first run is retained as incomplete. Flash verification alone is not proof of a running device.

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


## Current research outcome

The [sanitized research record](../training/reports/wake-v11-research.json) retains failures, rather than promoting a development pass into a release. N (B13+B14) and P (B13+H5) passed the reused development gate, but their separately generated independent tests still produced two false wakes each. These tests are consumed and hash-protected from training and subsequent selection. Neither candidate was installed as a normal release. The MN7 veto also failed: B14 retained one false wake, and the stronger B13 variant was rejected on its third negative replay.

A separate research encoder now uses authorized **original TRAIN** child-speech transcripts and fictional synthesis for tone-free phonetic CTC supervision. Its internal speaker-held-out phoneme error rate is 0.6815; that is not good ASR accuracy or wake acceptance. Q1's longer ordered head detected 299/316 development targets but falsely woke on 89/730 non-targets, so it was rejected. Phone-posterior and longer-context readouts remain experiments. Screened English sound spellings (`Pee Koo` / `Pee Coo`) retain their actual synthesis text; incorrect `pi ke`, `pi gu` and `PQ` outputs are not relabeled as targets.

`training/phonetic_pretrain.py` requires the existing local permission record and protected waveform hashes. `--phone-head` additionally verifies matching acoustic-encoder and phone-head checksums. These private restricted derivatives are not published. The household recordings remain test-only and were not scored during these candidate choices.


### Export and streaming diagnostics

`training/check_quantization.py` compares a SavedModel and its INT8 graph on content-hash-checked TRAIN speech before accuracy promotion. It rejects protected/held-out audio, records both model identities and fails when probability errors exceed declared engineering tolerances. The initial Q2b/Q2c comparisons exposed a backend disagreement, not evidence of export corruption: the same multi-output Dense graph ran near float on the optimized runtime and very differently on the pinned reference runtime. Dense weights are now exported per-tensor; the reference and static policies reject unverified per-channel FC graphs. A portable G re-export passed four TRAIN parity checks but still failed development (312/316 targets, 5/730 false wakes).

A separately declared 519-feature startup experiment retained the original cold failures. `evaluate_iteration.py --lead-seconds 6 --warmup-frames 519` scores only after a full recurrent horizon and five valid outputs, and records that changed context. This is a **rejected diagnostic**, not an original-gate pass: Q4 still produced 82/730 false wakes; Q3 still failed recall and false-wake requirements. No startup delay was installed on the normal device. The original default evaluation remains unchanged.

Frozen-encoder TRAIN-stream mining and residual-head experiments also failed. The current research hypothesis is a **short-context phonetic encoder**: `phonetic_pretrain.py --fresh --kernels 3,5,7` learns phone features from scratch with trainable normalization, using authorized original TRAIN transcripts only. The earlier long-context phonetic encoder's error rate is not carried over as a result for this new run. Independent V13 was consumed only after V11V was frozen. It failed as recorded below; V11, V12 and V13 are all protected from training and subsequent selection.


### Original-utterance phonetic continuation

The binary wake manifest included 297 mined child-speech prefixes. A negative wake label stays valid after cropping, but its inherited full transcript does not. Phonetic pretraining now excludes derived prefixes and augmented records. Earlier phone scores are retained as diagnostics with this defect disclosed; they are not clean-transcript acceptance.

The new private corpus uses 21,842 complete official TRAIN child utterances (15.43 hours), 502 original public adult clips and 122 content-screened synthetic clips. It was extracted from the already downloaded archive; official dev/test archives and household recordings were not opened for this preparation. Original child speaker hashes are preserved for the internal fold. MInDS-14 has no verified speaker identity and stays TRAIN-only. Bounded batch generators avoid duplicate full-corpus TensorFlow copies on the local laptop. No new wake candidate has qualified.

### Independent rejection and single-network follow-up

V11V combined B13 (189,936 bytes) and the early U phonetic verifier (90,296 bytes). Fixed causal replay and a development-selected contrast margin passed the original development gate: 295/316 targets, 0/730 false wakes, including 38/38 new originals and 184/203 pitch/tempo variants. The host Micro runtime matched all bytes on six TRAIN cases across three resets. This did **not** qualify the model: frozen V13 subsequently detected 34/37 targets and falsely woke on 2/44 non-targets. Adult Mandarin was 7/8, adult mixed 4/4, childlike Mandarin 13/14 and childlike mixed 10/11. V13 is now consumed; a later candidate requires a new independent test. Nothing was promoted to normal firmware.

W transfers the original-child acoustic encoder into one scalar-output wake network. `--sequence-readout --head-backbone-weights /private/zero-head-encoder.weights.h5` freezes that encoder and learns an ordered nonlinear readout; initialization and frozen-weight tests are included. It is 132,064 bytes and retains the existing firmware input/output shape. W detected 306/316 development targets but falsely woke on 32/730 non-targets. Its small TRAIN float/INT8 diagnostic also passed only 5/8 cases. W is rejected. U phonetic training continues on the original corpus; neither compilation nor a low CTC loss establishes wake acceptance.

The host checker optionally supports `MODEL FEATURES --trace-output TRACEFILE` for per-frame integer outputs over three resets. It supports scalar and small vector diagnostics; host allocation and parity are not ESP32 timing measurements.

An explicit `--train-sequence-encoder` experiment jointly fine-tunes the acoustic layers and ordered readout while freezing pretrained batch-normalization statistics and the integer identity anchor. Its tests verify that only the intended weights change. This is an opt-in research path; default sequence training freezes the encoder. X uses a later original-child checkpoint and this joint path. It detected 315/316 development targets but falsely woke on 58/730 non-targets; rejected.

Y adds opt-in `--contrastive-classes` to sequence training. Complete near phrases receive separate training classes; cropped prefixes remain generic negatives. A shared softmax exports only the target probability, retaining the scalar firmware ABI. Its initialization preserves 0.5 wake probability and tests verify training/inference weight sharing. Y passed all eight TRAIN float/INT8 diagnostics and exact host Micro byte comparison on six cases across three resets (host arena 80,320 bytes). It detected 304/316 development targets with 15/730 false wakes; the single network is rejected. A local pilot constructing phrases from public child TRAIN segments failed all 34 content screens and was excluded entirely; these are not natural wake recordings or new acceptance evidence.

### Z: causal agreement, independent test rejected

Z combines B13 and Y with explicit cutoffs 0.90/0.92, five-inference averages and a past-only ten-inference coincidence window. This uses the exact causal evaluator, not clip-maximum voting. It passed the unchanged development criteria: 295/316 targets, 0/730 false wakes, 46/46 legacy targets, 38/38 new originals and 184/203 pitch/tempo targets. The combined model files occupy 323,464 bytes. The cutoffs were selected on reused development audio; no household or consumed independent test selected them.

The candidate and runtime sources were frozen before generating independent V14: 128 preassigned fictional utterances with balanced adult/childlike conditions and literal English-name examples. Content screening precedes wake scoring. V14 was independently content-screened (103/128 accepted), then consumed once: 44/48 targets and 0/55 false wakes. Adult Mandarin was 14/14, adult mixed 7/9, childlike Mandarin 14/15 and childlike mixed 9/10. Literal-English subsets were 1/2 adult and 4/5 childlike. English recall failed; the freeze was archived and nothing was deployed. V14 is protected from subsequent training and selection. Existing ensemble defaults retain their original 0.8/0.8 behavior; use `--threshold-a .9 --threshold-b .92` only for the separately identified Z research contract. Two Micro interpreters must not invoke the global ESP-NN scratch buffer concurrently. ESP32 allocation, actual timing and human trials are still required. Full original-child phonetic continuation ended after 46 further epochs with internal phone error 0.4904; that remains research evidence, not a wake success rate.

AA/AB continue using new TRAIN synthesis only. An explicit English phonetic surface preserves its actual synthesis text and expected utterance separately; content screening requires the complete greeting and both nickname syllables, and rejects extra English words. Only 1/48 English-surface target generations passed, so the others were excluded. New reviewed Google material is merged with the original corpus using strict whole-batch rejection. The resulting addition has 60 TRAIN rows, including nine targets (five mixed); the original 1,046 development waveforms/labels are unchanged. Additional bounded Google requests collect adult and fictional childlike literal-English TRAIN material. These are data preparation and running experiments, not new results or real-child evidence.

### Continued capacity experiment

AA/AB and causal AC finished on the expanded TRAIN corpus. AA reached 305/316 targets with 7/730 false wakes; AB reached 300/316 with 16/730; both passed all eight TRAIN float/INT8 diagnostics. Their causal agreement reached 296/316 with 2/730 false wakes and failed the adult pronunciation groups. These candidates are rejected; no additional independent test was consumed.

AE increases phonetic capacity to 192 channels, a 96-channel stem and four causal kernels (3/5/7/9), with a 630 ms receptive field. It starts fresh on the same original child/adult corpus and fixed 58-class vocabulary, rather than reusing a failed wake score as a training label. `phonetic_pretrain.py --filters 192 --first-filters 96 --kernels 3,5,7,9` is explicit; the defaults remain 128/64. Optional `--feature-cache-source` requires the source protection ledger, exact corpus/phone/fold fingerprint and matching float32 arrays; all current source waveform hashes are still checked before reuse. This avoids recomputing or duplicating the original raw frontend cache. AE completed 23 epochs with early stopping. Full internal speaker-fold phoneme error was 0.5182, worse than U’s 0.4904; increasing capacity did not improve this acoustic metric. The 159,802-parameter training graph includes a 58-class phone head and training-only state; its checkpoint file is not the deployed wake model. AF/AG separately test frozen and jointly trained wake readouts, respectively, without consuming any new independent or household test. Actual INT8 wake size, Micro parity, ESP32 memory and timing remain unverified. The 512 KiB/256 KiB/30 ms deployment limits are unchanged.

The local Google project then returned a free-tier **daily** limit of 10 requests for the TTS model, despite 65-second pacing. Three individual clips were retained and content-screened; one target passed. Requests stopped until the reported reset; no paid fallback or quota rotation is used. This observed project limit is not a universal pricing claim.

AF finished 24 epochs: the frozen-encoder wake model is 263,488 bytes and detected 237/316 development targets with 11/730 false wakes. TRAIN float/INT8 diagnostics passed 6/8 cases. All six native Micro traces matched exactly across three resets, using 115,584 bytes of host arena; this is not ESP32 allocation or timing evidence. AF is rejected. AG jointly trains the acoustic encoder and readout on the same protected TRAIN data; household recordings remain unused.

AG completed 15 epochs: 312/316 development targets, 16/730 false wakes; its causal combination with B13 reached 301/316 and 1/730. Both are rejected. AG’s six native Micro traces matched exactly (115,584-byte host arena), but none of eight TRAIN float/INT8 diagnostics passed. Several calibrated activation ranges became coarse (a state scale of about 2.03 per integer level). This motivates the separate `--relu6 --sequence-readout --train-sequence-encoder` experiment: bound acoustic and readout activations at six, then explicitly retrain. This changes the model function; it is not a transparent conversion repair or an accuracy claim. Defaults remain unchanged. Weight preservation, actual clipping and full-window/streaming alignment have focused tests. AI uses the same protected TRAIN data and unchanged development gate.
