"""Bounded, checksummed USB replay for an offline command diagnostic image.

This module neither flashes hardware nor reads microphones. The caller owns the
serial connection and must enforce corpus provenance and restore normal firmware.
"""
import base64
import json
import time


def fnv1a(data):
    value = 2166136261
    for byte in data:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


class Probe:
    def __init__(self, serial, chunk=128, diagnostic=None):
        if chunk not in [128,256,512]:
            raise ValueError('Transport blocks must contain 128, 256 or 512 samples')
        self.serial, self.chunk, self.diagnostic = serial, chunk, diagnostic
        self.pending = b''

    def read_record(self, resynchronizing=False):
        chunk = self.serial.readline()
        if chunk and self.diagnostic:
            self.diagnostic(chunk)
        self.pending += chunk
        if len(self.pending) > 4096:
            self.pending = b''
            raise RuntimeError('Oversized probe response')
        if not self.pending.endswith(b'\n'):
            return None
        line, self.pending = self.pending, b''
        if b'Guru Meditation' in line or b'Task watchdog' in line:
            raise RuntimeError('Device runtime failed during command replay')
        if b'PROBE ' not in line:
            return None
        try:
            return json.loads(line.rsplit(b'PROBE ', 1)[1])
        except (ValueError, UnicodeError):
            if resynchronizing:
                return None
            raise RuntimeError('Malformed probe response') from None

    def receive(self, kind, value=None, timeout=5):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            result = self.read_record()
            if result is None:
                continue
            if result['kind'] == 'error':
                raise RuntimeError('Device rejected probe transport: ' + str(result['value']))
            if result['kind'] != kind or value is not None and result.get('value') != value:
                raise RuntimeError('Unexpected probe acknowledgement')
            return result
        raise TimeoutError(f'Missing command probe acknowledgement: {kind} {value}')

    def send(self, line):
        self.serial.write(line + b'\n')
        self.serial.flush()

    def reset(self):
        # Flush a possible truncated line, then start an explicit new protocol
        # session. Only this resynchronization ignores stale error/ACK records.
        self.pending = b''
        self.send(b'')
        self.send(b'R')
        until = time.monotonic() + 5
        while time.monotonic() < until:
            result = self.read_record(resynchronizing=True)
            if result and result.get('kind') == 'ready' and result.get('value') == 512:
                return
        raise TimeoutError('Command probe resynchronization failed')

    def replay(self, identifier, label, pcm):
        if not isinstance(pcm, bytes) or len(pcm) % 2 or not 0 < len(pcm) <= 320000:
            raise ValueError('Expected bounded mono little-endian PCM16')
        if not isinstance(identifier, int) or not 0 <= identifier <= 0xffffffff or label not in [0, 1]:
            raise ValueError('Invalid probe metadata')
        self.send(f'B {identifier} {label} {len(pcm)//2}'.encode())
        self.receive('begin', identifier)
        for seq, offset in enumerate(range(0, len(pcm), self.chunk * 2)):
            self.send(f'F {seq} '.encode() + base64.b64encode(pcm[offset:offset+self.chunk*2]))
            self.receive('frame', seq)
        checksum = fnv1a(pcm)
        self.send(f'E {checksum}'.encode())
        result = self.receive('result', timeout=30)
        if any(result.get(k) != v for k, v in
               {'id': identifier, 'label': label, 'samples': len(pcm)//2, 'checksum': checksum}.items()):
            raise RuntimeError('Replay identity or checksum mismatch')
        return result
