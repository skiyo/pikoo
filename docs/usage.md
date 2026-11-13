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

## Volume and display orientation

A new device starts at -24 dB. Set volume conservatively and test with the connected speaker:

```sh
python tools/device.py diagnose --port PORT --command 'volume -24'
python tools/device.py diagnose --port PORT --command 'rotate 90'
```

Volume accepts integer dB values from -50 to 0; 0 is the highest setting, not mute. Supported orientation commands are `rotate 90` and `rotate 270`. Saved settings survive same-layout upgrades. Speaker volume does not control microphone privacy; use mute for that.

## Everyday expectations

Pikoo needs network model services for conversation. Local wake and stored data do not turn the ESP into an offline language model. Searching is optional and provider-dependent; webpage reading is offered only with configured Tavily extraction. Audio/text sent during an active session is processed by your providers. Use explicit memory instructions and back up useful lists through USB.

[FAQ](faq.md) · [Troubleshooting](troubleshooting.md) · [Backup](firmware.md)
