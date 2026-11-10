#!/usr/bin/env python3
"""Run a loopback-only, silent HTTPS CONNECT / TLS / Live WebSocket check."""
import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time

TARGET = "api.openai.com"
API = "fake-pikoo-api"
PROXY = b"Basic " + base64.b64encode(b"fixture:proxy-only")
PCM = base64.b64encode(struct.pack("<640h", *([31] * 640))).decode()
STARTED = json.dumps({"type": "session.started", "session": {
    "audio": {"format": {"type": "audio/pcm", "rate": 16000}}
}}).encode()
AUDIO = json.dumps({"type": "session.output_audio.delta", "delta": PCM}).encode()


def read_exact(stream, n):
    data = bytearray()
    while len(data) < n:
        chunk = stream.recv(n - len(data))
        if not chunk:
            raise EOFError("peer closed")
        data.extend(chunk)
    return bytes(data)


def header(stream):
    data = bytearray()
    while len(data) < 8192:
        data += read_exact(stream, 1)
        if data.endswith(b"\r\n\r\n"):
            return bytes(data)
    raise ValueError("oversize header")


def frame(stream, data, masked=False, opcode=0x81):
    mask = os.urandom(4) if masked else b""
    bit = 128 if masked else 0
    length = bytes([len(data) | bit]) if len(data) < 126 else bytes([126 | bit]) + struct.pack("!H", len(data))
    payload = bytes(x ^ mask[i % 4] for i, x in enumerate(data)) if masked else data
    stream.sendall(bytes([opcode]) + length + mask + payload)


def read_frame(stream, masked=False):
    opcode, length = read_exact(stream, 2)
    assert bool(length & 128) == masked
    length &= 127
    if length == 126:
        length = struct.unpack("!H", read_exact(stream, 2))[0]
    assert length < 32768
    mask = read_exact(stream, 4) if masked else b""
    payload = read_exact(stream, length)
    return opcode, bytes(x ^ mask[i % 4] for i, x in enumerate(payload)) if masked else payload


def certificate(directory, name):
    key, cert = (directory / f"{name}.{ext}" for ext in ("key", "pem"))
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", f"/CN={name}", "-keyout", str(key), "-out", str(cert)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context, cert, key


class NestedTLS:
    def __init__(self, proxy, context, hostname):
        self.proxy = proxy
        self.incoming, self.outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.ssl = context.wrap_bio(self.incoming, self.outgoing, server_hostname=hostname)
        self.call(self.ssl.do_handshake)

    def flush(self):
        while self.outgoing.pending:
            self.proxy.sendall(self.outgoing.read())

    def call(self, operation, *args):
        while True:
            try:
                result = operation(*args)
                self.flush()
                return result
            except ssl.SSLWantWriteError:
                self.flush()
            except ssl.SSLWantReadError:
                self.flush()
                data = self.proxy.recv(16384)
                if not data:
                    raise EOFError("tunnel closed")
                self.incoming.write(data)

    def recv(self, n):
        return self.call(self.ssl.read, n)

    def sendall(self, data):
        while data:
            data = data[self.call(self.ssl.write, data):]


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextlib.contextmanager
def serve(handler):
    with Server(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join()


def live_fixture(tls, seen):
    class Live(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                with tls.wrap_socket(self.request, server_side=True) as stream:
                    self.session(stream)
            except (EOFError, ssl.SSLError, ConnectionError):
                pass

        def session(self, stream):
            request = header(stream)
            assert request.startswith(b"GET /v1/live/sessions HTTP/1.1\r\n")
            assert b"proxy-authorization" not in request.lower()
            fields = dict(line.split(b": ", 1) for line in request.split(b"\r\n")[1:] if b": " in line)
            auth = fields.get(b"Authorization")
            seen.append(auth)
            if auth != f"Bearer {API}".encode():
                code = 429 if auth == b"Bearer busy-fixture" else 401
                stream.sendall(f"HTTP/1.1 {code} Fixture\r\nContent-Length: 0\r\n\r\n".encode())
                return
            accept = base64.b64encode(hashlib.sha1(fields[b"Sec-WebSocket-Key"] +
                b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
            stream.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
            opcode, payload = read_frame(stream, masked=True)
            session = json.loads(payload)["session"]
            assert opcode == 0x81 and session["model"] == "gpt-live-1"
            frame(stream, STARTED)
            # Deliver one fragmented JSON event with fixture PCM.
            frame(stream, AUDIO[:50], opcode=0x01)
            frame(stream, AUDIO[50:], opcode=0x80)
    return Live


def fixture_relay(port, names):
    # A loopback-only SOCKS5 egress makes the fixed OpenAI authority resolve to
    # the local mock, without modifying system DNS or contacting OpenAI.
    class Socks(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                self.relay(self.request)
            except (EOFError, ConnectionError):
                pass

        def relay(self, client):
            assert read_exact(client, 1) == b"\x05"
            methods = read_exact(client, read_exact(client, 1)[0])
            assert 0 in methods
            client.sendall(b"\x05\x00")
            assert read_exact(client, 4) == b"\x05\x01\x00\x03"
            name = read_exact(client, read_exact(client, 1)[0]).decode()
            target_port = struct.unpack("!H", read_exact(client, 2))[0]
            assert (name, target_port) == (TARGET, 443)
            names.append(name)
            with socket.create_connection(("127.0.0.1", port), timeout=5) as upstream:
                client.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
                while True:
                    readable, _, _ = select.select([client, upstream], [], [], 5)
                    if not readable:
                        return
                    for src in readable:
                        data = src.recv(16384)
                        if not data:
                            return
                        (upstream if src is client else client).sendall(data)
    return Socks


@contextlib.contextmanager
def mihomo(binary, directory, config, port):
    path = directory / "mihomo.json"
    path.write_text(json.dumps(config))
    with (directory / "mihomo.log").open("w+") as log:
        process = subprocess.Popen([binary, "-d", directory, "-f", path], stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(log.read())
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=.1).close()
                    break
                except OSError:
                    time.sleep(.05)
            else:
                raise TimeoutError("Mihomo listener")
            yield process
        except Exception:
            log.seek(0)
            print(log.read()[-4000:], file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def client_context(cert):
    return ssl.create_default_context(cafile=str(cert))


@contextlib.contextmanager
def tunnel(proxy_port, proxy_ca, upstream_ca, metrics=None, authority=f"{TARGET}:443", auth=PROXY):
    start = time.perf_counter()
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=5) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with proxy_ca.wrap_socket(sock, server_hostname="localhost") as proxy:
            outer = time.perf_counter()
            headers = f"CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n".encode()
            if auth:
                headers += b"Proxy-Authorization: " + auth + b"\r\n"
            proxy.sendall(headers + b"\r\n")
            response = header(proxy)
            status = int(response.split(b" ")[1])
            connected = time.perf_counter()
            if status != 200:
                yield status, None
                return
            inner = NestedTLS(proxy, upstream_ca, TARGET)
            if metrics is not None:
                metrics.append([(outer - start) * 1000, (connected - outer) * 1000,
                                (time.perf_counter() - connected) * 1000])
            yield status, inner


def upgrade(stream, auth):
    key = base64.b64encode(os.urandom(16))
    stream.sendall(f"GET /v1/live/sessions HTTP/1.1\r\nHost: {TARGET}\r\n"
                   f"Authorization: Bearer {auth}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: ".encode() + key + b"\r\n\r\n")
    response = header(stream)
    if response.startswith(b"HTTP/1.1 101 "):
        expect = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
        assert b"Sec-WebSocket-Accept: " + expect + b"\r\n" in response
    return int(response.split(b" ")[1])


def wire_call(wire, op, **arguments):
    wire.stdin.write(json.dumps({"op": op, **arguments}) + "\n")
    wire.stdin.flush()
    return json.loads(wire.stdout.readline())


def rejection(action, exception):
    try:
        with action():
            pass
    except exception:
        return
    raise AssertionError("unexpected certificate acceptance")


def run(args):
    auths, destinations, metrics, first = [], [], [], []
    with tempfile.TemporaryDirectory(prefix="pikoo-net-") as temp, \
            subprocess.Popen([args.core, "--wire"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as wire:
        directory = Path(temp)
        upstream_tls, upstream_cert, _ = certificate(directory, TARGET)
        _, proxy_cert, proxy_key = certificate(directory, "localhost")
        with serve(live_fixture(upstream_tls, auths)) as live_port, serve(fixture_relay(live_port, destinations)) as socks:
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            config = {"mode": "rule", "log-level": "info",
                      "listeners": [{"name": "pikoo-edge", "type": "http", "listen": "127.0.0.1", "port": port,
                                     "certificate": str(proxy_cert), "private-key": str(proxy_key),
                                     "users": [{"username": "fixture", "password": "proxy-only"}]}],
                      "proxies": [{"name": "fixture", "type": "socks5", "server": "127.0.0.1", "port": socks}],
                      "rules": [f"AND,((IN-NAME,pikoo-edge),(DOMAIN,{TARGET}),(DST-PORT,443)),fixture",
                                "IN-NAME,pikoo-edge,REJECT", "MATCH,REJECT"]}
            outer, inner = client_context(proxy_cert), client_context(upstream_cert)
            with mihomo(args.mihomo, directory, config, port):
                rejection(lambda: tunnel(port, inner, inner), ssl.SSLCertVerificationError)
                rejection(lambda: tunnel(port, outer, outer), ssl.SSLCertVerificationError)
                with tunnel(port, outer, inner, auth=b"") as (status, _):
                    assert status == 407, status
                with tunnel(port, outer, inner, auth=b"Basic " + base64.b64encode(b"fixture:incorrect")) as (status, _):
                    assert status == 403, status
                for authority in ("blocked.test:443", f"{TARGET}:444"):
                    before = len(destinations)
                    try:
                        with tunnel(port, outer, inner, authority=authority) as (status, _):
                            assert status != 200
                    except (EOFError, ConnectionError):
                        # Mihomo may accept CONNECT, then close when routing
                        # rejects the destination. No mock egress was reached.
                        pass
                    assert len(destinations) == before
                for credential, expected in (("incorrect-fixture", 401), ("busy-fixture", 429)):
                    with tunnel(port, outer, inner) as (status, stream):
                        assert status == 200 and upgrade(stream, credential) == expected
            # Verify a dead proxy refuses, then restart on the same listener.
            try:
                with tunnel(port, outer, inner):
                    raise AssertionError("dead proxy accepted connection")
            except OSError:
                pass
            with mihomo(args.mihomo, directory, config, port):
                for cycle in range(args.cycles):
                    start = time.perf_counter()
                    if cycle % 25 == 0:
                        print(f"connection cycle {cycle + 1}/{args.cycles}", file=sys.stderr)
                    with tunnel(port, outer, inner, metrics) as (status, stream):
                        assert status == 200 and upgrade(stream, API) == 101
                        outgoing, = wire_call(wire, "connect")["send"]
                        frame(stream, outgoing.encode(), masked=True)
                        opcode, message = read_frame(stream)
                        assert opcode == 0x81 and wire_call(wire, "receive", message=message.decode())["ready"]
                        assert not wire_call(wire, "drain")["queued"]
                        opcode, first_part = read_frame(stream)
                        assert opcode == 0x01
                        opcode, last_part = read_frame(stream)
                        assert opcode == 0x80
                        assert wire_call(wire, "receive", message=(first_part + last_part).decode())["queued"] == 640
                        first.append((time.perf_counter() - start) * 1000)
                    assert not wire_call(wire, "close")["queued"]
        wire.stdin.close()
        assert wire.wait(timeout=3) == 0
    assert auths.count(f"Bearer {API}".encode()) == args.cycles and set(destinations) == {TARGET}
    def percentiles(values):
        values = sorted(values)
        return {str(p): round(values[(len(values) * p + 99) // 100 - 1], 3) for p in (50, 95)}
    print(json.dumps({"cycles_passed": args.cycles, "proxy_restart": True,
                      "outer_tls_ms": percentiles([m[0] for m in metrics]),
                      "connect_ms": percentiles([m[1] for m in metrics]),
                      "inner_tls_ms": percentiles([m[2] for m in metrics]),
                      "first_pcm_ms": percentiles(first),
                      "credentials_separated": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core")
    parser.add_argument("--mihomo", required=True)
    parser.add_argument("--cycles", type=int, default=100, choices=range(1, 1001), metavar="1..1000")
    run(parser.parse_args())
