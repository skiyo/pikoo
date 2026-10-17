"""Discover only this project's registered USB monitor; never kill processes."""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat

ROOT = Path(__file__).resolve().parents[1]


def registry_path(port):
    private = Path(os.environ.get('PIKOO_PRIVATE_DIR', str(Path.home()/'.config/pikoo')))
    return private/('monitor-'+hashlib.sha256(port.encode()).hexdigest()[:12]+'.json')


def registered_socket(port):
    path = registry_path(port)
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if record.get('port') != port or record.get('project') != str(ROOT):
        raise RuntimeError('USB monitor belongs to another project. Close it explicitly before proceeding.')
    target = Path(record['socket'])
    if not target.exists():
        return None
    info=target.stat()
    if info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode) or info.st_mode & 0o077:
        raise RuntimeError('USB monitor must be a private socket owned by this user.')
    return target


def command(target, value):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(target))
        client.sendall((value+'\n').encode())
        return json.loads(client.recv(8192))
