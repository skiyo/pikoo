# Body control

2.0.0 fixes conflicting model arguments and voice routing/result delivery. Model settings use explicit `mode` and `value`; USB retains the legacy single-field format.

Directions follow the view of a person facing Pikoo: left/right commands select that side of the installed screens. The board maps logical eye selection and horizontal gaze to its wiring and mounting.

## Automated real-speech acceptance

On macOS, play synthetic speech through the computer speakers into the real Pikoo microphone:

```sh
python tools/generate-body-voice.py --out /tmp/pikoo-voice-fixtures
python tools/test-body-voice.py --port /dev/cu.usbmodem1101 --audio-dir /tmp/pikoo-voice-fixtures --out /absolute/private/voice-results.json
```

Tingting and Samantha system voices are required. The device must hear the computer clearly. Passing requires the expected actual result, exactly one write and return of the tool receipt. Every three cases the test exports recent history to check spoken feedback. `*-history.private.json` may contain ambient transcripts and must remain private.

After addressee classification, body candidates may be routed locally to the reasoning Agent. Keywords only select a foreground task; they never directly execute hardware. Negation, quotation and ambiguity still require intent validation. Each applied step publishes verified progress immediately while the foreground task can continue remaining actions. Final replies retain completed receipts even if later reasoning fails.

Pikoo 2.1 controls the existing dual eye displays, speaker, microphone and button. Tools execute on the ESP32; spoken understanding uses the configured Live and reasoning services. No camera, IMU, touch sensor or mechanical movement is included.

## Everyday commands

Wake Pikoo with “Hi, Pikoo”, then speak in English or Chinese.

| Command | Behavior |
|---|---|
| Turn your volume up / down a little | Change codec gain by +3 / −3 dB |
| Set volume to fifty percent | Set the control scale to 50%, equivalent to −25 dB gain |
| Make your eyes brighter / dimmer | Change both backlights by 10 percentage points |
| Turn your eye backlights off | Set brightness to zero; microphone state is independent |
| Smile / look curious / look sleepy | Temporary expression, normally 3 seconds |
| Blink / wink your left eye / wink your right eye | One 350 ms action |
| Look left / right / forward | Rendered gaze, normally 2 seconds |
| Stop speaking | Cancel the current reply and remain available |
| Go to sleep | End the conversation and return to local wake standby |
| Turn off your microphone | Disable capture; restore with the existing button hold or USB `unmute` |

The volume percentage is a control scale, not an acoustic pressure ratio. Codec gain is bounded to −50…0 dB; it is not a dB SPL measurement. Volume and brightness change only on explicit requests and persist across reboot. Expressions and gaze expire without Flash writes. New actions replace the same channel. Explicit expression/gaze durations are bounded to 10 seconds. Microphone-off, connection and error states remain visible.

A smile is silent unless laughter is explicitly requested. Gaze does not imply seeing an object. With backlights off, wake Pikoo and request “set eye brightness to one hundred percent” to recover.

## USB tools

Close other serial monitors first. Use a Python environment with `pyserial`. Run these commands from the repository root and replace the port.

```sh
python tools/body.py --port /dev/cu.usbmodem1101 body_get_state
python tools/body.py --port /dev/cu.usbmodem1101 body_set_audio '{"delta_db":3}'
python tools/body.py --port /dev/cu.usbmodem1101 body_set_display '{"percent":70}'
python tools/body.py --port /dev/cu.usbmodem1101 body_perform '{"action":"happy","duration_ms":3000}'
python tools/body.py --port /dev/cu.usbmodem1101 body_perform '{"action":"blink_left"}'
```

Logical interfaces are `body.get_state`, `body.set_audio`, `body.set_display` and `body.perform`. Wire function names use underscores for provider compatibility. Model settings use explicit `mode` and `value`, for example `{"mode":"delta_db","value":3}`. Audio modes are `gain_db`, `delta_db` or `percent`; display modes are `percent` or `delta_percent`. USB also accepts the legacy single-field form. Conflicting settings are rejected. Percentages are integers from 0 to 100. Volume maps through `round(-50 + percent/2)`.

Actions: `happy`, `curious`, `drowsy`, `neutral`, `blink`, `blink_left`, `blink_right`, `look_left`, `look_right`, `look_front`, `stop_speaking`, `sleep`, `mute_microphone`. Optional `duration_ms` affects expressions and gaze; blinks always last 350 ms.

`applied` confirms application of a setting or temporary action. `saved` confirms a persistent preference write; temporary actions normally return `saved:false`. A `persistence_failed` result means the setting applied but may revert after reboot. `hardware_failed` must not be presented as success. State reports actual codec gain, backlight setting, session, microphone and temporary actions, not measured sound pressure or ambient light.

The last 64 process-local call receipts prevent duplicate relative adjustments with the same call ID. Reboot clears this cache. Reusing an ID with different arguments returns a conflict. Each manual USB command is a new request. Cancellation and reconnect clear transient actions, preserving volume and brightness.

## Development and acceptance

With ESP-IDF 5.5.5 activated:

```sh
bash tools/test-body.sh
bash tools/test-eyes.sh
bash tools/build-body-host.sh
python tools/body-preview.py --out /tmp/pikoo-body-preview
```

Open the generated `index.html` and select an action. Frames come from the shared C++ controller and renderer; they do not validate physical brightness, acoustics or timing. Optional `tools/test-body-semantics.py --config /absolute/private/config.json --out /tmp/semantic-results.json` uses the configured paid reasoning service to check 30 direct commands and six negated/quoted commands without executing hardware actions.

Back up and verify the full Flash before upgrading. Use `tools/device.py upgrade` to replace only the application partition. Keep private backups and credentials outside public artifacts. Hardware acceptance requires visual inspection, listening, echo/interruption checks and two-hour/eight-hour runs. Unfinished tests remain pending in the [acceptance record](body-verification.md).
