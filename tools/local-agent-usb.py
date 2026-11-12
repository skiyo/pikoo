#!/usr/bin/env python3
"""Provision or transfer Pikoo's single-device state over USB serial."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
import time

import serial
from usb_serial import preserve_lines

MAX_SNAPSHOT = 24 * 1024
SNAPSHOT = b"PIKOO_AGENT_SNAPSHOT "


def wait_for(port, prefix, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = port.read_until(size=MAX_SNAPSHOT + len(SNAPSHOT) + 64)
        if prefix in line:
            return line.split(prefix, 1)[1].strip()
        if b"agent usb result=rejected" in line:
            raise SystemExit("Device rejected the operation. Check firmware, muted state and NVS.")
    raise SystemExit("Timed out waiting for the device. Close other USB monitors and retry.")


def provision():
    host = input("Mihomo TLS hostname: ").strip()
    port = int(input("Mihomo TLS port [8443]: ").strip() or "8443")
    audio_rate = int(input("GPT-Live PCM rate [16000]: ").strip() or "16000")
    if audio_rate not in (16000, 24000):
        raise SystemExit("PCM rate must be 16000 or 24000.")
    name = input("Mihomo username: ").strip()
    password = getpass.getpass("Mihomo password: ")
    key = getpass.getpass("OpenAI device project key: ")
    return json.dumps({"proxy_host": host, "proxy_port": port,
                       "proxy_basic": base64.b64encode(f"{name}:{password}".encode()).decode(),
                       "api_key": key, "audio_rate": audio_rate}, separators=(",", ":")).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="USB serial device")
    parser.add_argument("operation", choices=("provision", "import", "export", "legacy", "forget", "reboot"))
    parser.add_argument("file", type=Path, nargs="?")
    args = parser.parse_args()
    if (args.operation in ("import", "export")) != (args.file is not None):
        parser.error("provide a file for import or export")
    if args.operation == "export" and args.file.exists():
        parser.error("choose a new output file")
    if args.operation == "provision":
        payload = provision()
    elif args.operation == "import":
        with args.file.open("rb") as source:
            data = source.read(2 * MAX_SNAPSHOT + 1)
        if len(data) > 2 * MAX_SNAPSHOT:
            parser.error("snapshot is too large")
        payload = json.dumps(json.loads(data), ensure_ascii=False, separators=(",", ":")).encode()
        if len(payload) > MAX_SNAPSHOT:
            parser.error("snapshot is too large")
    else:
        payload = None

    device = serial.Serial(port=None, baudrate=115200, timeout=1, write_timeout=10)
    device.dtr = False
    device.rts = False
    device.port = args.port
    with device:
        preserve_lines(device)
        device.reset_input_buffer()
        deadline = time.monotonic() + 25
        next_request = 0.0
        while True:
            if time.monotonic() >= next_request:
                device.write(b"\nmute\nstatus\n")
                next_request = time.monotonic() + .5
            line = device.read_until(size=8192)
            if b"diag: board=" in line and b"muted=1 " in line and b"upload=0 " in line and b"state=5 " in line:
                break
            if time.monotonic() >= deadline:
                raise SystemExit("Device did not reach muted standby before USB transfer.")
        device.write(f"agent {args.operation}\n".encode())
        if payload is not None:
            wait_for(device, b"agent usb ready")
            for index in range(0, len(payload), 128):
                device.write(payload[index:index + 128])
                time.sleep(.02)
            device.write(b"\n")
        if args.operation == "export":
            data = wait_for(device, SNAPSHOT)
            json.loads(data)
            fd = os.open(args.file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(data + b"\n")
            print("Snapshot saved. The device is muted.")
        elif args.operation == "reboot":
            wait_for(device, b"agent usb result=ok_reboot")
            print("Device reboot requested.")
        else:
            wait_for(device, b"agent usb result=ok_reboot")
            print("Saved. Reboot the device to apply the change.")


if __name__ == "__main__":
    main()
