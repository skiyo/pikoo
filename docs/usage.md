# Using Pikoo

**English** | [简体中文](usage.zh-CN.md)

## Start, speak and stop

With valid configuration and an unmuted device, say **“Hi, Pikoo”**. Wake detection runs locally; wait for the greeting before asking a question. Network availability and provider response time affect readiness. The default language is English; `agent.language: "zh-CN"` selects Chinese without changing the wake phrase.

| Control | Effect |
|---|---|
| BOOT short press | Wake from standby; stop an active answer |
| BOOT double press | End the conversation and clear short-term context |
| BOOT hold | Toggle microphone mute |
| RESET | Restart with saved configuration and stored data |
| Spoken interruption | Cancel the current work and queued speech when recognized |
| Farewell | Finish goodbye playback and return to local standby |

Natural-language recognition is probabilistic. Use BOOT or USB `stop`/`end` when an immediate explicit action is needed. Mute clears playback and closes the session. Inactive sessions close after 60 seconds. Explicit End clears recent context; ordinary idle sleep retains bounded context.

## Try the local tools

- “Add apples to the shopping list.” Then “Read the shopping list without changing it.”
- “Add water the plants to my todo list.” Then “Remove water the plants from my todo list.”
- “Remember explicitly that I prefer short answers.” Then “What have I asked you to remember?”
- “Replace apples with green apples on the shopping list.”
- “Search the web for …” after enabling a search provider.

Check the reply before assuming a write succeeded. A network failure after a successful local commit does not undo that commit; read the list before repeating a request. Clear-all operations require confirmation. Lists are shared by the device; Pikoo does not recognize speakers or maintain separate accounts.

## Control the speaker and eyes

After waking Pikoo, use the commands below. Volume and brightness change and persist only on explicit requests; expressions, blinks and gaze are temporary.

| Command | Actual behavior |
|---|---|
| “Turn your volume up / down a little” | Increase / decrease codec gain by 3 dB; report limits honestly |
| “Set volume to fifty percent” | Set the control scale to 50%, equivalent to −25 dB gain |
| “Make your eyes brighter / dimmer” | Adjust both backlights by 10 percentage points |
| “Turn your eye backlights off” | Set brightness to zero without changing microphone or session state |
| “Smile / look curious / look sleepy” | Hold the expression for 3 seconds, then restore the conversation expression |
| “Blink / wink your left eye / wink your right eye” | One binocular or single-eye action, about 350 ms |
| “Look left / right / forward” | Change rendered gaze for 2 seconds, then restore it |
| “Stop speaking” | Stop playback and cancel the current reply, remaining available |
| “Go to sleep” | End the conversation, close the eyes and return to local wake standby |
| “Turn off your microphone” | Disable capture; restore with BOOT hold or USB `unmute` |

Directions follow the view of a person facing the screens. Explicit expression and gaze durations are limited to 10 seconds; a new action replaces the same channel. Requested actions override natural expressions, while microphone-off, connection and error states remain visible. A smile changes only the eyes; explicitly request laughter for sound. The displays are not cameras, and gaze does not imply seeing an object.

Codec gain ranges from −50 to 0 dB; 0 dB is the highest setting, not mute. The percentage is a control scale, not a sound-pressure ratio or dB SPL measurement. New devices start at −24 dB; upgrades retain existing preferences. Backlight brightness ranges from 0 to 100%. With the lights off, wake Pikoo and request “set eye brightness to one hundred percent”. Reducing volume or brightness does not disable the microphone.

## USB settings and recovery

When voice services are unavailable, use USB to query actual state or restore brightness:

```sh
python tools/body.py --port PORT body_get_state
python tools/body.py --port PORT body_set_audio '{"gain_db":-24}'
python tools/body.py --port PORT body_set_display '{"percent":100}'
python tools/device.py diagnose --port PORT --command 'unmute'
python tools/device.py diagnose --port PORT --command 'rotate 90'
```

Orientation supports `rotate 90` and `rotate 270`. Same-layout upgrades retain volume, brightness and mounting orientation. Rotation calibrates the installation; everyday left/right commands move only the gaze. USB and voice share the body executor; see the [tool contract](family-tools.md) for interfaces and receipts.

## Everyday expectations

Pikoo needs network model services for conversation. Local wake and stored data do not turn the ESP into an offline language model. Searching is optional and provider-dependent; webpage reading is offered only with configured Tavily extraction. Audio/text sent during an active session is processed by your providers. Use explicit memory instructions and back up useful lists through USB.

[FAQ](faq.md) · [Troubleshooting](troubleshooting.md) · [Backup](firmware.md)
