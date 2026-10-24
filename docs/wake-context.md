# Continuous-context wake diagnostics

[English](wake-context.md) | [简体中文](wake-context.zh-CN.md)

## Finding on 2026-10-24

The BM17 engineering model remains unqualified. A controlled development probe
reproduced sensitivity to ordinary speech immediately before the wake phrase.
This is a model/pipeline weakness, **not an established explanation of the
household's intermittent misses**. A silent 90-second prefix did not reproduce
the failure in the initial two-target probe.

The subsequent complete development check used all 195 existing targets and
a separate deterministic 30-second prefix assembled from TRAIN non-targets:

| Condition | Adult synthetic hits | Childlike synthetic hits |
|---|---:|---:|
| Cold, 1-second silence | 97/101 | 89/94 |
| Speech directly before target | 42/101 | 24/94 |
| Speech, 0.3-second gap | 65/101 | 41/94 |
| Speech, 1-second gap | 95/101 | 90/94 |

The cold total is 186/195, matching the earlier clip-based development result.
The adjacent-speech condition is much worse. The target set includes correlated
pitch/tempo derivatives. These counts do not establish human recognition rates
or a production pass. See the [sanitized report](../training/reports/wake-context-20261024.json).
The full check also covered 712 non-targets: zero cold false wakes, but the
same childlike non-target activated in each of the three speech-prefix
conditions. These are correlated replays of one clip, not three independent
false-wake events. Thus the current model also fails the new context check.

An earlier 24-target isolation diagnostic kept the model and five-inference
0.90 cutoff fixed:

| Prefix before the target | Adult synthetic hits | Childlike synthetic hits |
|---|---:|---:|
| 1 second of silence | 12/12 | 12/12 |
| 5 seconds of ordinary speech, no gap | 7/12 | 7/12 |
| 90 seconds of ordinary speech, no gap | 6/12 | 4/12 |
| Same 90 seconds, then 1 second of silence | 12/12 | 12/12 |
| Same 90 seconds, then 3 seconds of silence | 12/12 | 12/12 |

These are the same 24 existing development targets in every condition, not
independent trials, speakers or real-child acceptance. The speech prefix was
concatenated authorized ChildMandarin **TRAIN non-target** audio, not household
audio and not simultaneous background mixing. Its reuse does not measure a
false-wake rate per hour. No prefix windows exceeded the threshold in this
probe. Model-only resets recovered 11/12 adult and 12/12 childlike targets;
frontend-only resets recovered 8/12 and 6/12. Neither reset experiment proves
a safe firmware fix. Periodic resets could introduce recognition blind spots.

The model SHA-256 is
`383f3bc8f49302e1a9e8d45aff517cf107d6c3e888d81ca33d690f18f21fb4b2`.
Weights and licensed audio stay local. No model, microphone gain or wake
threshold was changed during this investigation. Fresh device telemetry showed
successful local wake, no inference errors and no dropped wake blocks; that
snapshot does not exclude other microphone or enclosure effects.

## Reproduce the development check

The pinned [training environment](../training/requirements.txt) is required.
Use a reviewed development manifest and a private protected-audio hash ledger:

```sh
python training/evaluate_context.py \
  --model /private/candidate.tflite \
  --manifest /private/reviewed-development/manifest.json \
  --protected-hashes /private/protected-recordings.json \
  --prefix-seconds 30 --gaps 0,0.3,1 --include-non-targets \
  --output /private/context-development.json
```

The tool uses all validation targets and a deterministic shuffled prefix of
non-target recordings. It uses the same reference kernels and input rounding
as the firmware. It never scores the test split. Household/evaluation-only
manifests and protected waveform copies are rejected. Reports record hashes,
prefix selection, style, source, background threshold windows and target
scores. Background windows are not counted as target hits or independent
false-wake events. Decision windows crossing the prefix/target boundary are
excluded from target scores. A report with `completed=false` is partial.
`--include-non-targets` also checks all validation near-words and ordinary
speech after the same prefixes; their activations are false wakes, not recall.

Cold, adjacent-speech and short-gap results must remain separate in future
candidate comparisons. Any resulting training change must use authorized
TRAIN data, pass the original recall/false-wake checks and continuous-context
development checks, then freeze before new independent and physical testing.
Do not lower the threshold or tune using household acceptance recordings.

## Offline training experiment

`train.py --speech-context-probability 0.5` explicitly replaces the idle lead
on half of TRAIN positive examples with ordinary TRAIN speech and a 0–300 ms
gap. An extra speech prefix warms frontend state before the retained causal
window. The complete target and completion tail remain intact. Only authorized
ChildMandarin/MInDS TRAIN non-targets supply context, with a fixed independent
random seed and hash checks. The new option defaults to zero, preserves the
baseline random sequence and evaluation construction, and changes the feature
cache key when enabled. This is a training hypothesis, not a deployed fix.

The positive-only six-epoch experiment A improved cold streaming targets from
186/195 to 193/195 but introduced **14/712 non-target false wakes**; it failed
the original gate and was not flashed. `--speech-context-negatives` explicitly
applies the same probability to TRAIN non-targets as well, including near-words.
Experiment B tests this balanced construction from the original checkpoint;
it does not inherit A's weights.

A's adjacent-speech result was 99/101 adult and 93/94 childlike targets,
compared with the baseline's 42/101 and 24/94. This confirms a useful direction
but does not offset its false wakes. Its adjacent-speech non-target false wakes
totaled 19/712, compared with 1/712 for the baseline. See the
[failed A report](../training/reports/wake-context-a-20261024.json).

B reduced cold false wakes to 4/712, with 187/195 targets. Its adjacent-speech
result was 185/195 targets and 3/712 non-target false wakes. It also failed the
complete 181-recording supplemental development gate, including English-name
groups; it was not flashed. See the [failed B report](../training/reports/wake-context-b-20261024.json).

The bounded experiment C starts from A's stronger positive-recognition
checkpoint, retaining balanced speech context and adding 136 causal hard
negative prefixes mined from **all 9,534 TRAIN non-targets** with B. Of those,
98 are real Chinese child ordinary-speech negatives, not child wake positives.
Mining never reads validation, independent tests or household recordings. C
must pass the same original, full supplemental and continuous-context checks;
training completion alone does not authorize deployment.

C finished eight epochs and failed with 189/195 cold targets and 3/712 false
wakes; the full supplement scored 63/72 targets, including failures in the
adult/childlike English-name groups. D reused the exact C feature cache and
kept A's batch-normalization parameters/statistics fixed during training. It
also failed: 188/195 cold targets, 4/712 false wakes and 60/72 supplementary
targets. The shared training/scalar-view normalization freeze has a regression
test. Neither model proceeded to the full continuous-context check after
failing prerequisite gates; neither was flashed.

See the [C report](../training/reports/wake-context-c-20261024.json) and
[D report](../training/reports/wake-context-d-20261024.json). All 907 manifest
validation clips retain bitwise-identical features in C/D. The 20 generated
internal validation noise windows differ from A/B because the expanded TRAIN
set advances the random generator; external streaming gates retain the original
manifest and do not use these windows. C and D use identical arrays.

The three C false wakes are pitch/tempo derivatives of the same existing
development phrase, “给我讲一个故事”. They remain failures. New TRAIN-only
utterances of that category and content-audited name examples are the next
data experiment; validation recordings are never copied into training.

## TTS content quality

The small new corpus uses the [official Gemini TTS interface](https://ai.google.dev/gemini-api/docs/speech-generation),
with text and `speech_metadata` separated. Requests are paced at 30 seconds,
without retries after quota errors. Eight new Flash TTS clips were generated;
all four target clips failed the local content screen (for example, “皮克” or
“Pico” instead of the complete pi/ku target). They are quarantined, not relabeled
or trained. ASR is a content screen, not human pronunciation/age acceptance.
The project's Flash TTS API returned a free-tier limit of ten requests/day;
that model was stopped. A separate bounded Flash-Lite experiment uses explicit
first-tone homophone text and undergoes the same strict content review. This
does not change the supported wake phrase.

Both ASR content screens approved two Flash-Lite childlike TRAIN targets, and
human listening confirmed that both complete name syllables use first tones.
These are two clips from one fictional voice, not real child recordings or
wake-model acceptance. Two adult Flash-Lite targets had conflicting ASR results
and stayed quarantined. Three newly synthesized ordinary-speech negatives
passed both screens. Together with four reviewed near-words, the nine new TRAIN
clips entered E. E still failed: 186/195 cold targets, 2/712 false wakes, and
64/72 supplemental targets. Literal-English name groups scored 11/13 adult and
6/9 childlike. It was not flashed; see the [E report](../training/reports/wake-context-e-20261024.json).

## Fast-speech training hypothesis

Some missed supplemental targets have only about 0.8–1.1 seconds of active
speech. This motivates a separate TRAIN-only tempo experiment; it does not
establish the cause of household misses. `prepare_voice_variants.py --fast-speech`
explicitly permits tempo up to 2.0 and rejects any non-TRAIN input, evaluation
flags or protected recording hashes. The default tempo limit remains 1.25.
Pitch-preserving duration and split protection have regression tests.

F adds two independently content-screened 3.1 Flash TTS adult targets, then
uses deterministic hash selection of 64 original TRAIN clips per style/label
bucket (adult/childlike, target/non-target), with at most eight per prompt/voice
group and 0.9–2.6-second source duration. The 256 sources produce 512 derivatives
at 1.4× and 1.8× tempo, without pitch shift. Both target and near-word negatives
receive the changes. No development recording is transformed or copied into
training. Correlated derivatives are augmentation, not new independent speakers
or child acceptance. F retains the fixed threshold and all prerequisite gates;
training and a small file size do not establish an acceptable release.

F completed eight epochs with the same 192,688-byte export. It failed with
186/195 cold targets, 5/712 false wakes, and 61/72 supplemental targets. The
literal-English groups scored 9/13 adult and 6/9 childlike. All 907 original
manifest validation features remain bitwise-identical. The small eight-TRAIN-case
float/INT8 check passed, but the full streaming gates failed; no independent or
physical test followed. See the [F report](../training/reports/wake-context-f-20261024.json).
This bounded combined continuation does not prove that tempo augmentation
generally cannot help. It was not flashed.

A separate content-only audit now covers the **entire 181-recording supplement**,
without using model scores to select clips. It checks fictional TTS with another
ASR model. The first eight-utterance request produced eight valid reviews, but
the next response had a different utterance count and was rejected without
assigning labels. Subsequent requests explicitly use `--batch-size 1`, with
30 seconds between requests; the eight valid cached reviews are retained.
Quota/API errors still stop the run. Exact transcript screening also rejects
unexpected English or digits instead of erasing them during normalization;
alignment and content guards have regression tests.
No household or independent wake-test recordings are included.
ASR disagreements require inspection; they do not authorize deleting failed
model scores or calling a corrected corpus an independent test. Existing gates
and manifests remain unchanged.
