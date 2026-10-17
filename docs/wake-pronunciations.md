# Wake pronunciation development

[English](wake-pronunciations.md) | [简体中文](wake-pronunciations.zh-CN.md)

The accepted phrase includes Mandarin **你好皮酷 (pí kù)** and mixed-language **你好 Pikoo (pī kū / PEE-koo)**. The embedded classifier consumes audio, not spelling. Changing a transcript or shifting overall pitch does not add the missing pronunciation.

The current Google-only candidate excludes macOS and local TTS training positives. `prepare_level_tones.py` applies Praat PSOLA to the last two voiced regions of reviewed isolated Google speech, then screens the result again. These are **prosody derivatives**, not fresh native mixed-language recordings or real children. Uncertain alignment/content is rejected. Parent identities retain their splits. Separate local synthetic voices are only an additional development challenge for this candidate. NVIDIA NIM/Magpie is excluded.

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
