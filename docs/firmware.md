# Firmware installation, updates and USB maintenance

**English** | [简体中文](firmware.zh-CN.md)

## Choose the operation

| Operation | Writes | Prerequisite |
|---|---|---|
| `backup` | A private full-Flash file on the computer | New backup directory, stable USB |
| `install` | Checked board images and supplied configuration | Verified backup matching this board, matching build metadata |
| `upgrade` | Application only for the same partition layout | Matching device/build partition tables |
| `configure` | Complete service configuration; then reboot | Valid private JSON |
| Family `export` / `import` | Read / replace family snapshot | Muted standby; private file |
| `forget` | Remove service configuration including Wi-Fi | Reboot afterward; family data retained |
| `restore` | All 16 MiB from backup | Same-board verified backup; overwrites current data |

The [quick start](getting-started.md) provides the full first-install sequence. Run commands from the package root with pyserial/esptool installed. Select one USB port and close competing monitors. The interactive alternative is `python tools/usb-setup.py`; use `--language zh-CN` for Chinese prompts.

## Build artifacts and partitions

Build using ESP-IDF 5.5.5 and `bash tools/build-device.sh "$PWD/models/hi-pikoo/hi_pikoo.tflite"`. Images and `flasher_args.json`/`pikoo-board.json` must come from the same build. The installer checks board identity, image ranges and partition layout. The standalone release BIN is application-only.

| Partition | Purpose |
|---|---|
| `nvs` | Device settings such as volume/orientation |
| `phy_init` | Radio initialization data |
| `factory` | Application, 6 MiB, offset `0x20000` |
| `model` | Model resources, 4 MiB |
| `agent_secret` | Replaceable Wi-Fi/service configuration |
| `agent_data` | Local lists, explicit memory, context and write receipts |

Use the checked installer rather than manually guessing offsets. Routine configuration does not require full erase, Flash encryption provisioning or eFuse changes.

## Upgrade and configuration update

Export useful data before an upgrade, then:

```sh
python tools/device.py upgrade --port PORT --build firmware/build-dualeye --dry-run
python tools/device.py upgrade --port PORT --build firmware/build-dualeye
python tools/device.py configure --port PORT --config /absolute/private/device.json
python tools/device.py diagnose --port PORT --command status
python tools/device.py diagnose --port PORT --command unmute
```

Only run `configure` if settings need updating. Same-layout upgrades retain configuration, family data, volume and orientation. A layout mismatch is a stop condition, not permission to erase the device. Inspect the intended board/build and follow the backed-up installation procedure.

## Export and import data

```sh
python tools/local-agent-usb.py --port PORT export /absolute/private/family.json
python tools/local-agent-usb.py --port PORT import /absolute/private/family.json
python tools/local-agent-usb.py --port PORT reboot
python tools/device.py diagnose --port PORT --command unmute
```

Export requires a new output file, excludes service credentials and leaves the device muted. The file still contains private lists/memory/context. Import **replaces** the snapshot; it is not a merge. Export the destination's current data before importing when it must be retained. The import limit is 24 KiB after normalization. Reboot applies imported state; then read back the expected entries.

## Remove credentials or recover a board

```sh
python tools/local-agent-usb.py --port PORT forget
python tools/local-agent-usb.py --port PORT reboot
```

This removes service settings, including Wi-Fi, while preserving family data. Re-provision to use cloud services again. For full same-board recovery:

```sh
python tools/device.py restore --port PORT --backup /absolute/private/board-backup --dry-run
python tools/device.py restore --port PORT --backup /absolute/private/board-backup
```

Restore overwrites all Flash, including newly created data and credentials. The command verifies the restored bytes; reset the board if it remains in download mode. Keep backups private. No automatic family-data merge or cross-board full-Flash migration is provided.

## Diagnostic commands

`device.py diagnose` supports `status`, `wake`, `stop`, `end`, `mute`, `unmute`, `tone`, volume and orientation commands. `wake` can open a paid service session and `tone` produces sound; neither belongs in a silent check. Maintenance tools use muted standby and preserve USB control-line handling. If a port changes after reboot, list devices again instead of repeatedly writing to the old name.

[Troubleshooting](troubleshooting.md) · [Context and storage](context-memory.md)
