# Troubleshooting

**English** | [简体中文](troubleshooting.zh-CN.md)

Work from the earliest failing layer: USB → configuration → Wi-Fi/TLS → voice → reasoning/tools → playback. Change one setting at a time. Do not erase Flash as a first diagnostic step.

## Collect a safe status snapshot

```sh
python -m serial.tools.list_ports
python tools/device.py diagnose --port PORT --command status
```

Record the firmware version, state, muted/upload state and error code. Keep API keys, complete configuration and family content out of public reports. Close competing serial monitors before opening a new one.

| Symptom | What to check | Next step |
|---|---|---|
| No USB port | Data cable, direct connection, power, OS device permissions | Re-list ports; try a known data cable; inspect board power |
| Port exists but busy/times out | Another monitor or application holds the port | Close it; use one maintenance process; re-list after reset |
| `MIC OFF` | Mute state, especially following USB export/configuration | Send `unmute`; do not rebuild |
| `USB SETUP` | Missing/invalid configuration | Validate the private JSON, run `configure`, inspect status |
| Wi-Fi cannot connect | 2.4 GHz SSID/password, signal and access restrictions | Correct configuration; try a normal reachable network |
| TLS fails | Endpoint hostname, certificate chain, device time and network | Repair certificate/connectivity; verification cannot be disabled |
| HTTP 401/403 | Which service failed, key validity, model permission | Replace only that service's settings, then retry |
| HTTP 429 | Provider rate/quota limits | Check provider usage; allow backoff; avoid rapid manual retries |
| Voice works, tools fail | Independent LLM URL/model/key and function support | Inspect backend error; test a read-only list request |
| No search tool | `search.enabled`, selected protocol | Enable search with its own settings; re-provision |
| Cannot read a webpage | Tavily extraction enabled, same origin, HTTPS target | Check `extract_url`; unsupported adapters cannot read arbitrary URLs |
| Broken speech | Wi-Fi jitter, streaming errors, playback queues, heap | Lower concurrent load; collect counters; test at low volume |
| Silent speaker | Mute, volume, connector and supply | Verify wiring/power, unmute; acoustic check only when appropriate |
| Wrong display orientation | Saved mounting direction | Use `rotate 90` or `rotate 270` |
| Installation says backup mismatch | Backup does not match present device contents | Stop; retain old backup and create a new verified backup if intentional |
| Upgrade says partition mismatch | Image/layout not appropriate for this device | Use the documented backed-up installation flow |

## USB transfer rejected

The transfer utility requires muted standby with upload disabled. It requests that state automatically before sending a snapshot or configuration. If the device rejects or times out, inspect status, ensure no active monitor is competing, and confirm compatible firmware. Import must be a valid snapshot under 24 KiB after normalization. Export requires a new output filename. Import and forget need reboot before use.

## Wake and audio diagnosis

Test the complete “Hi, Pikoo” phrase in a quiet setting at a natural distance. A short press can distinguish a wake-detection issue from a network/conversation issue. Repeatedly shouting the phrase, changing thresholds blindly or playing synthetic clips does not establish natural wake reliability. Check microphone openings, speaker wiring and final-enclosure acoustics. Sound tests should be explicitly planned; normal desktop checks are silent.

For intermittent gaps, record whether queue underruns, frame-send errors, reconnects or heap pressure occur. A desktop latency number is not the provider latency on your Wi-Fi. Do not claim a fix based only on an eye animation or a successful HTTP request.

## Recovery and escalation

If a reset changes the USB device name, select the new port. Full-Flash restore overwrites configuration and data and belongs to recovery, not routine updating; see [firmware](firmware.md). If problems persist, submit exact reproduction steps and redacted diagnostics with the board and build identity. [FAQ](faq.md) explains expected behavior; [security](../SECURITY.md) covers private reporting.
