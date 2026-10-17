#!/usr/bin/env python3
"""USB installation, bounded upgrades, diagnostics and exact factory recovery.

Run in ESP-IDF 5.5.5's Python environment. Private artifacts stay outside Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from monitor_control import registered_socket, command as monitor_command

ROOT = Path(__file__).resolve().parents[1]
FLASH_SIZE = 16 * 1024 * 1024


def partitions(raw):
    result = {}
    for pos in range(0, min(len(raw), 0xC00), 32):
        magic, kind, subtype, offset, size, label, flags = struct.unpack_from('<HBBII16sI', raw, pos)
        if magic in (0xFFFF, 0xEBEB):
            break
        if magic != 0x50AA:
            raise ValueError('Invalid partition table')
        name = label.split(b'\0')[0].decode('ascii')
        if not size or offset + size > FLASH_SIZE or name in result:
            raise ValueError('Invalid partition bounds')
        result[name] = dict(kind=kind, subtype=subtype, offset=offset, size=size, flags=flags)
    if not result:
        raise ValueError('Empty partition table')
    ranges = sorted((p['offset'], p['offset']+p['size']) for p in result.values())
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError('Overlapping partitions')
    return result


def build_files(build):
    build = build.resolve()
    description = json.loads((build/'project_description.json').read_text())
    if description.get('target') != 'esp32s3' or description.get('project_name') != 'pikoo':
        raise ValueError('Expected Pikoo dual-eye ESP32-S3 build')
    marker=json.loads((build/'pikoo-board.json').read_text())
    if marker != {'board':'waveshare-dualeye-1.28','flash_bytes':FLASH_SIZE,'layout':1}:
        raise ValueError('Expected non-touch DualEye board build and layout version 1')
    args = json.loads((build/'flasher_args.json').read_text())
    files = []
    for address, name in args['flash_files'].items():
        p = (build/name).resolve()
        offset = int(address, 16)
        if not p.is_relative_to(build) or not p.is_file() or offset < 0 or offset+p.stat().st_size > FLASH_SIZE:
            raise ValueError('Invalid build image path or bounds')
        files.append((offset, p))
    table = partitions((build/'partition_table/partition-table.bin').read_bytes())
    expected = {'nvs': (0x9000, 0x10000), 'factory': (0x20000, 6*1024*1024)}
    for key, (offset, size) in expected.items():
        if key not in table or (table[key]['offset'], table[key]['size']) != (offset, size):
            raise ValueError('Unexpected Pikoo partition layout')
    nvs = table['nvs']
    for start, p in files:
        end = start+((p.stat().st_size+4095)//4096)*4096
        if start < nvs['offset']+nvs['size'] and end > nvs['offset']:
            raise ValueError('Build images would overwrite private NVS')
    return files, table


def checked_backup(folder):
    raw = folder/'factory-full.bin'
    manifest = json.loads((folder/'manifest.json').read_text())
    if raw.stat().st_size != FLASH_SIZE or hashlib.sha256(raw.read_bytes()).hexdigest() != manifest['full_backup_sha256']:
        raise ValueError('Factory backup checksum or size mismatch')
    return raw


def esptool(port, *args):
    # Capture output; only return a concise result. No credential material is printed.
    command = [sys.executable, '-m', 'esptool', '--chip', 'esp32s3', '--port', port, '--baud', '460800', *map(str, args)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError('USB operation failed; check cable, selected port and download mode. '+result.stdout[-1500:])
    return result.stdout


def write(port, images, keep_download=False):
    args = ['--after', 'no_reset' if keep_download else 'hard_reset', 'write_flash']
    for address, p in images:
        args.extend([hex(address), str(p)])
    esptool(port, *args)
    print('Flash write and device digest verification passed.')


def serial_command(port, command, seconds=3):
    import serial
    s = serial.Serial(port=None, baudrate=115200, timeout=.1)
    s.dtr = False
    s.rts = False
    s.port = port
    s.open()
    raw = bytearray()
    try:
        until = time.monotonic()+1
        while time.monotonic() < until:
            raw.extend(s.read(4096))
        s.write((command+'\n').encode())
        s.flush()
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            raw.extend(s.read(4096))
    finally:
        s.close()
    # Diagnostic firmware prints no secrets; exclude general framework logs.
    for line in raw.decode(errors='replace').splitlines():
        if 'diag:' in line or 'wake:' in line or 'pikoo:' in line:
            print(line)


def release_monitor(port):
    target=registered_socket(port)
    if not target:
        return
    monitor_command(target,'end')
    time.sleep(.2)
    monitor_command(target,'close-monitor')
    until=time.monotonic()+3
    while target.exists() and time.monotonic()<until:
        time.sleep(.05)
    if target.exists():
        raise RuntimeError('Pikoo monitor did not release USB. Close it before flashing.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['install', 'upgrade', 'configure', 'restore', 'diagnose'])
    p.add_argument('--port', required=True)
    p.add_argument('--build', type=Path, default=ROOT/'firmware/build-dualeye')
    p.add_argument('--config', type=Path)
    p.add_argument('--backup', type=Path)
    p.add_argument('--command', default='status', choices=['status', 'wake', 'stop', 'end', 'mute', 'unmute', 'takeover', 'tone', 'volume low', 'volume normal', 'volume higher','volume louder','rotate 90','rotate 270'])
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    os.umask(0o077)
    if a.action == 'diagnose':
        if not a.dry_run:
            monitor = registered_socket(a.port)
            if monitor:
                result=monitor_command(monitor,a.command)
                print('Command queued through the existing USB monitor; serial connection preserved.')
                print(json.dumps(result.get('status',{}).get('device',{}),indent=2))
            else:
                serial_command(a.port, a.command)
        return
    backup = None
    if a.action in ('install', 'restore'):
        if not a.backup:
            p.error('A verified private factory backup folder is required')
        backup = checked_backup(a.backup)
    if a.action == 'restore':
        if a.dry_run:
            print('Full 16 MiB recovery backup validated; no device accessed.')
            return
        release_monitor(a.port)
        write(a.port, [(0, backup)], keep_download=True)
        esptool(a.port, '--before', 'no_reset', 'verify_flash', '0x0', backup)
        print('All 16 MiB restored and verified against the factory backup.')
        return
    files, table = build_files(a.build)
    if a.action in ('install', 'configure'):
        from configure import validate
        if not a.config:
            p.error('Private --config is required; create it with the local setup tool')
        validate(json.loads(a.config.read_text()))
    if a.dry_run:
        print('Dual-eye build, image ranges, partition layout and private inputs validated; no device accessed.')
        return
    release_monitor(a.port)
    # Both operations inspect the device layout first. Installation also proves
    # the current device matches its backup, before overwriting any sectors.
    with tempfile.TemporaryDirectory(prefix='pikoo-usb-') as tmp:
        current = Path(tmp)/'table.bin'
        esptool(a.port, '--after', 'no_reset', 'read_flash', '0x8000', '0x1000', current, '--no-progress')
        actual = partitions(current.read_bytes())
        if a.action in ('upgrade', 'configure'):
            if actual != table:
                raise ValueError('Device partition layout differs. Use the backed-up first-install flow.')
            if a.action == 'configure':
                nvs = Path(tmp)/'private.nvs.bin'
                subprocess.run([sys.executable, str(ROOT/'tools/configure.py'), '--config', str(a.config), '--output', str(nvs)], check=True, stdout=subprocess.DEVNULL)
                write(a.port, [(table['nvs']['offset'], nvs)])
                print('Private configuration updated; existing conversation identifier cleared.')
                return
            application = [(offset, f) for offset, f in files if offset == table['factory']['offset']]
            if len(application) != 1 or application[0][1].stat().st_size > table['factory']['size']:
                raise ValueError('Invalid application image')
            write(a.port, application)
        else:
            esptool(a.port, '--before', 'no_reset', '--after', 'no_reset', 'verify_flash', '0x0', backup)
            nvs = Path(tmp)/'private.nvs.bin'
            subprocess.run([sys.executable, str(ROOT/'tools/configure.py'), '--config', str(a.config), '--output', str(nvs)], check=True, stdout=subprocess.DEVNULL)
            # All required images exist before entering the one write operation.
            write(a.port, files+[(table['nvs']['offset'], nvs)])
    print('Pikoo restarted. Run diagnose to inspect startup without exposing credentials.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as e:
        raise SystemExit(str(e))
