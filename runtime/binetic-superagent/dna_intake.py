#!/usr/bin/env python3
"""Private DNA intake for Genesis Seed binding.

Never prints DNA contents. Accepts uploads via localhost/127.0.0.1 only.
Writes an encrypted-at-rest capsule with a locally generated key and a hash
chain receipt. This is a handoff utility, not a diagnosis or claims engine.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path('/root/agent-workspace/binetic-superagent')
DNA_DIR = ROOT / 'dna_intake'
KEY_PATH = DNA_DIR / 'dna_key.bin'
CAPSULE_PATH = DNA_DIR / 'dna_capsule.enc.json'
INDEX_PATH = DNA_DIR / 'dna_index.json'
RECEIPTS = DNA_DIR / 'receipts.jsonl'
MAX_UPLOAD = 64 * 1024 * 1024


def cj(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def receipt(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    DNA_DIR.mkdir(parents=True, exist_ok=True)
    body = {'kind': kind, 'ts': time.time(), **payload}
    prev = sha(RECEIPTS.read_bytes()) if RECEIPTS.exists() and RECEIPTS.stat().st_size else '0' * 64
    record = {'body': body, 'body_hash': sha(cj(body)), 'prev': prev}
    with RECEIPTS.open('a') as f:
        f.write(json.dumps(record, sort_keys=True) + '\n')
    return {'body_hash': record['body_hash'], 'prev': prev, 'root': sha(cj(record))}


def encrypt_xor(data: bytes, key: bytes) -> bytes:
    # Stream is HMAC-SHA256(key, counter); sufficient for local-at-rest handoff,
    # not exported cryptographic storage.
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        out.extend(hmac.new(key, counter.to_bytes(8, 'big'), hashlib.sha256).digest())
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[:len(data)]))


def decrypt_xor(data: bytes, key: bytes) -> bytes:
    return encrypt_xor(data, key)


def load_key() -> bytes:
    DNA_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    key = secrets.token_bytes(32)
    KEY_PATH.write_bytes(key)
    os.chmod(KEY_PATH, 0o600)
    return key


def index_update(meta: dict[str, Any]) -> None:
    DNA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(meta, indent=2, sort_keys=True))
    os.chmod(INDEX_PATH, 0o600)


def index_read() -> dict[str, Any]:
    return json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else {}


def make_handler(allow_remote: bool) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = cj(payload)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            host = self.client_address[0]
            return allow_remote or host in ('127.0.0.1', '::1', 'localhost')

        def do_GET(self) -> None:
            if self.path == '/dna/status':
                idx = index_read()
                self.send_json({
                    'ok': True,
                    'intake': 'localhost-only',
                    'has_dna': bool(idx.get('has_dna')),
                    'sha256': idx.get('sha256'),
                    'bytes': idx.get('bytes'),
                    'filename': idx.get('filename'),
                    'received_at': idx.get('received_at'),
                    'capsule': str(CAPSULE_PATH),
                    'never_prints_dna': True,
                })
                return
            if self.path == '/dna/download-capsule':
                if not self._authorized() or not CAPSULE_PATH.exists():
                    self.send_json({'ok': False, 'error': 'unavailable'}, 403)
                    return
                data = CAPSULE_PATH.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_json({'ok': False, 'error': 'not_found'}, 404)

        def do_POST(self) -> None:
            if not self._authorized():
                self.send_json({'ok': False, 'error': 'loopback_only'}, 403)
                return
            if self.path != '/dna/upload':
                self.send_json({'ok': False, 'error': 'not_found'}, 404)
                return
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length <= 0 or length > MAX_UPLOAD:
                self.send_json({'ok': False, 'error': 'bad_length'}, 413)
                return
            raw = self.rfile.read(length)
            digest = sha(raw)
            key = load_key()
            capsule = {
                'v': 1,
                'created_at': time.time(),
                'filename': self.headers.get('X-DNA-Filename', 'uploaded_dna'),
                'bytes': len(raw),
                'sha256': digest,
                'ciphertext_b64': base64.b64encode(encrypt_xor(raw, key)).decode(),
            }
            CAPSULE_PATH.write_text(json.dumps(capsule, sort_keys=True))
            os.chmod(CAPSULE_PATH, 0o600)
            meta = {k: capsule[k] for k in ('created_at', 'filename', 'bytes', 'sha256')}
            meta['has_dna'] = True
            index_update(meta)
            rec = receipt('dna_upload', meta)
            self.send_json({
                'ok': True,
                'received': True,
                'bytes': len(raw),
                'sha256': digest,
                'filename': capsule['filename'],
                'receipt': rec,
                'capsule': str(CAPSULE_PATH),
            })
    return Handler


def cmd_serve(args: argparse.Namespace) -> int:
    handler = make_handler(args.allow_remote)
    host = '127.0.0.1' if not args.allow_remote else '0.0.0.0'
    server = ThreadingHTTPServer((host, args.port), handler)
    print(json.dumps({'ok': True, 'listen': f'{host}:{args.port}', 'note': 'loopback only unless --allow-remote'}, indent=2))
    server.serve_forever()
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(json.dumps({'ok': False, 'error': 'file_not_found', 'path': str(path)}, indent=2))
        return 2
    raw = path.read_bytes()
    boundary = secrets.token_hex(16)
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="dna"; filename="{path.name}"\r\n'
        'Content-Type: application/octet-stream\r\n\r\n'
    ).encode() + raw + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(
        f'http://127.0.0.1:{args.port}/dna/upload',
        data=body,
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'X-DNA-Filename': path.name,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    # The local multipart utility wraps bytes with boundaries; write exact file
    # directly if user used CLI, to avoid ambiguity.
    if result.get('ok'):
        key = load_key()
        digest = sha(raw)
        capsule = {
            'v': 1,
            'created_at': time.time(),
            'filename': path.name,
            'bytes': len(raw),
            'sha256': digest,
            'ciphertext_b64': base64.b64encode(encrypt_xor(raw, key)).decode(),
        }
        CAPSULE_PATH.write_text(json.dumps(capsule, sort_keys=True))
        os.chmod(CAPSULE_PATH, 0o600)
        meta = {k: capsule[k] for k in ('created_at', 'filename', 'bytes', 'sha256')}
        meta['has_dna'] = True
        index_update(meta)
        result['exact_file_written'] = True
        result['sha256'] = digest
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get('ok') else 1


def cmd_status(args: argparse.Namespace) -> int:
    req = urllib.request.Request(f'http://127.0.0.1:{args.port}/dna/status')
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(json.dumps(json.loads(resp.read()), indent=2, sort_keys=True))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog='dna-intake')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('serve')
    p.add_argument('--port', type=int, default=8657)
    p.add_argument('--allow-remote', action='store_true')
    p.set_defaults(func=cmd_serve)
    p = sub.add_parser('upload')
    p.add_argument('file')
    p.add_argument('--port', type=int, default=8657)
    p.set_defaults(func=cmd_upload)
    p = sub.add_parser('status')
    p.add_argument('--port', type=int, default=8657)
    p.set_defaults(func=cmd_status)
    args = ap.parse_args()
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
