# Family wake trials

English | [简体中文](wake-family-trials.zh-CN.md)

Updated 2026-11-03. These tools prepare future acceptance; no family trial was
performed by this change. The current frozen candidate still lacks a completed
fresh independent TEST and ESP32 runtime acceptance. Family participation remains
deferred until the user is ready.

`tools/wake-trials.py` uses the project's already registered USB monitor. It does
not open another serial connection, record audio, train, flash, change volume, or
send a simulated wake command. Formal trials use **Hi, Pikoo**, accepting piku or
piko with natural connected speech. The legacy Chinese prompt is diagnostic only.

## Before a formal run

Complete the sealed six-cohort independent TEST first. A formal run requires its
150-case report and completed consumption marker, the frozen model and policy,
and a verified installed-firmware manifest. The manifest must explicitly contain
`offline_qualified: true`, `firmware_version`, `app_sha256`, `model_sha256`, and
`policy_sha256`. A compiled image alone is not a verified installation. The
report must meet all six 20-target group gates, zero false/early wakes, and the
800ms latency gate; adult-only or partial reports are refused before USB access.

The running firmware reports model and policy file hashes in its existing
diagnostic record. These and the version must match the manifest throughout the
run. An old image without these fields cannot qualify as a verified formal run.

After the person explicitly says they are ready, run one person and one session:

```sh
python3 tools/wake-trials.py \
  --port "$PORT" --socket "$MONITOR_SOCKET" --status-file "$STATUS_FILE" \
  --firmware-manifest "$PRIVATE/verified-install.json" \
  --wake-model "$PRIVATE/hi_pikoo.tflite" --wake-policy "$PRIVATE/wake-policy.json" \
  --sealed-test-report "$PRIVATE/independent-test-report.json" \
  --tester child --tester-id child-1 --session-index 1 --trials 20 \
  --output "$PRIVATE/child-1-session-1.json"
```

Use private paths outside the repository. Omitting `--ready` preserves an
interactive readiness prompt. No countdown or recording starts merely by reading
this guide. Use `adult-1`, `adult-2`, `child-1`, `child-2` and session 1 or 2;
roles are user-declared, never inferred from a voice.

## What counts

The tool mutes during computer instructions and enables offline wake-test
isolation before unmuting. A silent green terminal cue replaces an acoustic
signal that could itself trigger the detector. Activity before that cue is not
credited to the target. Identity changes, lost isolation, resets, upload deltas,
inference errors or dropped work cannot produce a passing run. On interruption,
cleanup mutes before disabling the isolation gate; a failed mute leaves the gate
in place. Explicit short `--diagnostic` runs never report formal acceptance and
leave the microphone muted.

Machine counts remain **unconfirmed**, even at 18/20. An observer must separately
confirm one complete natural call per attempt, no adult follow-along or repeats,
and a one-metre distance. Save that statement in a private JSON file containing:

```json
{
  "report_sha256": "SHA256_OF_ORIGINAL_RUN_JSON",
  "tester_id": "child-1",
  "session_index": 1,
  "observed_at_unix": 0,
  "human_statement": "Describe what was actually observed after the run.",
  "all20_independent_complete_targets_once": true,
  "no_adult_follow_or_repeated_calls": true,
  "distance_m": 1
}
```

Replace the hash and timestamp with actual values; the timestamp must follow the
run. Do not fill affirmative fields when uncertain. `confirm` creates a separate
annotated file and preserves the original trial rows:

```sh
python3 tools/wake-trials.py confirm \
  --report "$PRIVATE/child-1-session-1.json" \
  --observation "$PRIVATE/child-1-session-1-observation.json" \
  --output "$PRIVATE/child-1-session-1-confirmed.json"
```

Finally use `family --run FILE` eight times with distinct confirmed runs and
`--output FILE`. The summary requires all four people in two nonoverlapping
sessions, each at least 18/20, on one verified model/policy/application. It does
not imply the separate eight-hour false-wake or ESP32 resource gates passed.
The `confirm` and `family` commands only read/write files; neither uses USB or audio.
