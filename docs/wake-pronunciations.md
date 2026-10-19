# Wake pronunciation development

[English](wake-pronunciations.md) | [简体中文](wake-pronunciations.zh-CN.md)

**Scope updated by the user on 2026-10-19:** the only required phrase is Mandarin **你好** followed by **Pikoo (pī kū / PEE-koo)**, with both name syllables first tone. The former pí kù variant is unspecified: it is neither required to wake nor required to be rejected. Adult and real-child acceptance, false-wake and resource requirements remain. Historical dual-pronunciation failures below remain failures. The embedded classifier consumes audio, not spelling. Changing a transcript or shifting overall pitch does not add the missing pronunciation.

The earlier V9B/C Google-only candidates excluded macOS and local TTS training positives. `prepare_level_tones.py` applies Praat PSOLA to the last two voiced regions of reviewed isolated Google speech, then screens the result again. These are **prosody derivatives**, not fresh native mixed-language recordings or real children. Uncertain alignment/content is rejected. Parent identities retain their splits. Separate local synthetic voices are only an additional development challenge for this candidate. NVIDIA NIM/Magpie is excluded.

V9 adds fictional synthetic voices. `generate_google.py --mixed-pronunciation` preserves preassigned Google voice splits and stops on quota errors. `generate_local_tts.py` uses explicitly downloaded Qwen3 VoiceDesign weights, with networking disabled and no reference recordings. Chinese spellings 批枯 / 披哭 constrain pī kū; wrong or uncertain output stays excluded. Source weight revisions/checksums are recorded separately.

Local prompt families are split before generation; a voice-design prompt does not guarantee a fixed voice or an independent real speaker. Pitch/tempo derivatives retain parent splits. Real child corpus examples remain ordinary-speech negatives, not child target positives.

`review_local_corpus.py` checks content with local Qwen3-ASR, without target hotwords. It verifies hashes and rejects household/evaluation/reference audio. If an earlier independent review exists, both must agree. The screen accepts pi/ku name homophones but rejects gu, gou, ke and qiu substitutions. ASR spelling cannot verify tone, age or human wake performance.

Household recordings remain evaluation-only: no training, augmentation, tuning, quantization or candidate selection. `train.py --protected-hashes /private/ledger.json` checks protected waveform hashes before caches and calibration. Iterate on public/synthetic development data, freeze before acceptance scoring, and report failures. Previously inspected household recordings are not a pristine blind test.

The target remains 18/20 at one metre per household member, with children scored separately, plus background false-wake and real-device checks. Synthetic scores cannot meet it alone. Restricted corpus files, private manifests, household audio, weights and firmware containing those weights stay local.

Optional local generation/review uses a separate Apple Silicon environment pinned in [requirements-local-audio.txt](../training/requirements-local-audio.txt); TensorFlow keeps its own [environment](../training/requirements.txt). Large offline ASR/TTS models are workstation tools, never ESP32 dependencies.

## Results on 2026-10-17

All three candidates failed the development gate. **None was flashed**; the device retains V8D.

| Candidate | Model bytes | Development target hits | False wakes on non-targets |
|---|---:|---:|---:|
| V9A: mixed synthetic experiment | 45,128 | 198/216 | 4/565 |
| V9B: Google training positives | 45,128 | 88/103 | 1/490 |
| V9C: wider channels and incomplete-prefix negatives | 62,640 | 87/103 | 2/498 |

The datasets differ, so aggregate recall does not rank these models directly. V9C's false wakes came from incomplete phrases; it detected only 12/25 additional local synthetic voice challenges. The Google level-tone groups scored 12/12, but these correlated derivatives do not establish natural mixed-name or child performance. All three had zero false wakes on 390 real Chinese child ordinary-speech negatives; there are no real child target recall results.

V9B/C use Google and its derivatives for current training positives, while inheriting the historical V8D initialization. The threshold remains 0.90 with five-inference averaging. Household audio was not used to select these candidates. See the [sanitized V9 report](../training/reports/wake-v9-summary.json).

The free Google TTS daily quota is exhausted. The next attempt must wait until at least 2026-10-18 08:00 Asia/Shanghai, then stop if still limited, without polling or paid fallback. NVIDIA NIM was cancelled at the user's request: no NIM speech was generated or used, and the newly created local credential file was deleted. The next step needs independently generated, content-checked natural pronunciation, rather than only a larger model or a lower threshold.

## Results on 2026-10-18: expanded mixed-name development

The V10 round uses reviewed Google speech plus existing offline Qwen3 VoiceDesign/ASR tools. No new large models were downloaded and no NVIDIA NIM/Magpie was used. The 36 fictional synthesis conditions were assigned to 24 training and 12 development groups before generation. Of 288 planned utterances, 287 had valid audio; 242 passed the transcript screen. Thirteen ambiguous near-name negatives were quarantined before broad-candidate training, leaving 229 approved originals. Their derivatives preserve parent splits. These are fictional adult/childlike styles, not recordings of real children or proof of English-native pronunciation.

Matching TRAIN-only ambiguous contrasts were withheld; all 813 legacy validation waveforms remain. The newer corpus retains 390 real Chinese child ordinary-speech negatives. No household recording was loaded, scored, or used for training, tuning, calibration or selection this round. The old macOS/self-test TRAIN positives were removed from the current data; checkpoint ancestry and historical development regressions still retain earlier sources.

A further 304 transcript-screened incomplete prefixes were cut from the exact same synthetic target waveforms (219 training, 85 development). This addresses voice differences between separately synthesized positive and negative utterances. Alignment uncertainty, full names, and unrelated ASR output are rejected. Human listening confirmed that one development negative says only “你好皮”, without “酷”; it remains negative. That is a synthetic-label check, not household training.

Candidate results and the unchanged software gate are recorded in the [sanitized V10 report](../training/reports/wake-v10-summary.json). D/E use 316 targets and 645 non-targets; F/G add 85 prefix negatives. Counts from different corpora must not be ranked directly. The fixed gate requires zero development false wakes, at least 90% in each new style/pronunciation group, at least 44/46 original targets, the augmentation check, and a model below 64 KiB. Passing this gate would still require board timing, household and background acceptance.

The F timing diagnostic found all 25 false-wake maxima after the 120 ms training tail. `train.py --negative-tail-seconds 1.2` is the G experiment: sample TRAIN non-target windows through a longer quiet period, retaining positive alignment and the streaming evaluation. This is a development hypothesis, not a proven explanation of real child failures. No lower threshold, dropped validation errors, or automatic deployment is used.

Small free Google requests admitted six isolated content-screened utterances; incomplete output, incorrect content and invalid batches were excluded. Quota responses and a transcription timeout/503 stopped further API attempts. This does not establish a provider outage. There is no scheduled retry or paid fallback. The next iteration needs better phonetic discrimination as well as broader natural speech, not merely more copies of a failing sample.

### Reproducing the public workflow

Use the pinned optional local-audio environment and already acquired model files. Keep generated audio, model weights and private manifests outside public releases. These commands illustrate the stages; corpus permission, parent splits and the protected household hash ledger remain mandatory.

```sh
python training/generate_local_tts.py --model /private/qwen3-tts \
  --output training/data/fictional-broad --broad --limit 288
python training/review_local_corpus.py --model /private/qwen3-asr \
  --manifest training/data/fictional-broad/manifest.json \
  --protected-hashes /private/household-hashes.json \
  --output training/data/fictional-broad/review.json
python training/prepare_tts_prefixes.py \
  --manifest training/data/reviewed-targets/manifest.json \
  --protected-hashes /private/household-hashes.json \
  --output training/data/matched-prefixes
# Independently review the prefixes before merging them with --reviewed-prefixes.
```

`prepare_google_iteration.py --context-frames 399` excludes only TRAIN positives that cannot fit whole with the configured speed jitter. `--quarantine-training-negatives` is an explicit label-quality exclusion for TRAIN data; it never removes legacy validation failures. `prepare_voice_variants.py --profile 3 1.0` can select a mild three-semitone derivative instead of the default five profiles. `evaluate_iteration.py` reports style, pronunciation and source separately; the standard streaming score remains the five-inference mean at 0.90. Host Micro parity and static size/operator checks are separate from actual ESP32 timing.

### Outcome of this round

**No V10 candidate passed the full development gate; none was flashed. The device retains V8D.** Expanding data improves some fictional childlike and mixed-name groups, but does not establish real child acceptance. D/E and F/G/H use different negative sets, so compare their detailed reports on matching subsets.

| Candidate | Bytes | Development target hits | False wakes |
|---|---:|---:|---:|
| V10D | 45,128 | 290/316 | 10/645 |
| V10E | 62,640 | 288/316 | 9/645 |
| V10F | 62,640 | 286/316 | 25/730 |
| V10G | 62,640 | 273/316 | 5/730 |
| V10H | 62,640 | 287/316 | 7/730 |

G reduces false wakes from F's 25/730 to 5/730 on the same set, but loses target recall. The human-confirmed “你好皮” negative drops from 0.9375 in F to 0.7836 in G, below 0.90. This is one corrected development error, not a general success. H tests longer complete-target tails (up to 0.6 s, capped to preserve the entire phrase and idle lead) alongside G's longer non-target tails. Its separate result above is also a failed candidate; the confirmed “你好皮” negative rises again to 0.9328 and falsely wakes. The specific incomplete-phrase problem therefore remains unresolved.

All D–H models passed static operator/size checks and host Micro score/reset parity (six cases, three resets each). The wider models use 26,704 bytes of host Micro arena; that is not whole-device memory or ESP32 timing. Software regression passed: 22 simulator, 9 server, 11 USB-tool and 45 training tests, plus native session/audio and eye checks. Actual children, one-metre wake trials and eight-hour background listening remain pending. Household audio was not scored this round.

## Larger-network follow-up on 2026-10-18

The user authorized a 512 KiB experimental budget. Continued larger-network training, exact streaming checkpoint selection and measured ESP32 resource results are tracked in [capacity development](wake-capacity.md) and the [V11 report](../training/reports/wake-v11-summary.json). Work is in progress; the normal device retains V8D until a candidate passes.

The new `training/level_tone_scope.py prepare` contract keeps every existing non-target and only explicitly labeled `mixed-pi1-ku1` positives. It does not relabel former positives. The reviewed corpus retains 663 TRAIN positives and 9,525 TRAIN negatives; development retains 184 targets and all 730 non-targets. `dualeye-pikoo-level-v1.json` requires 90% recall for raw adult, raw childlike, augmented and overall target groups, with zero development false wakes. Raw childlike voices remain synthetic. Missing development negatives or protected recordings fail closed. This is a new disclosed development scope, not a fresh independent test or retroactive release. AJ fine-tunes the existing 128/64-channel primary encoder on this scope; its results, INT8 compatibility, new frozen-candidate independent test and real-device/family trials are pending.

AJ finished 13 epochs: 182/184 first-tone development targets and 24/730 false wakes. Raw adult and fictional childlike targets were 18/18 and 24/24; those are synthetic development results. Seven of eight TRAIN float/INT8 diagnostics passed. All six native Micro traces matched exactly across three resets, with a 51,504-byte host arena; ESP32 timing remains unverified. AJ is rejected. AK mines causal prefixes from the 9,525 existing TRAIN negatives only (score at least 0.7, up to 500 prefixes and four per speaker), then increases negative loss weight and hard-negative repetition. No development or household waveform is mined or trained; the 914-case development contract is unchanged.

The AK mining pass examined all 9,525 TRAIN negatives and retained 500 causal prefixes, including 362 from public child speech. No validation/test/household recording was mined. V15 now preassigns 128 entirely new fictional test conditions: 32 first-tone targets and 32 negatives per adult/childlike style, with new prompt groups and seeds. No V15 audio has been generated or scored; freeze a qualifying model and runtime before generation. These synthetic conditions do not establish real-child performance.

AK reduced false wakes to 4/730 with 177/184 targets, but raw adult synthetic recall was 16/18. A bounded export-only comparison of saved epochs 1/4/7/10 found epoch 7 at 167/184 and 0/730, with adult recall 15/18. A 64-unit frozen-encoder residual head (AM) retained those same results and passed all eight TRAIN float/INT8 diagnostics and six native Micro traces; it still failed the adult group. No fresh test or household recording was scored. Google returned one new content-approved TRAIN utterance on the next quota day, then another explicit daily free-tier 429; requests stopped without fallback. `generate_local_tts.py --level-contrasts` now preassigns 96 TRAIN-only Chinese phonetic targets and matched near-phrase negatives across eight adult and four fictional childlike prompt families, using the existing offline Qwen3 weights. These prompts/seeds are disjoint from V11–V15 test plans. AP generation and AQ content-screened training are pending; this is not a claim of improvement.
