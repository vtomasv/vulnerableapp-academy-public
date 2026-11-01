#!/usr/bin/env python3
"""Cliente local del taller; no necesita herramientas instaladas en el host."""
from __future__ import annotations
import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import ProxyHandler, Request, build_opener

API_ROOT = 'http://academy:8000'
SESSION_FILE = Path.home() / '.config' / 'va-lab' / 'session.json'
OPENER = build_opener(ProxyHandler({}))


def _session():
    try:
        data = json.loads(SESSION_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_session(value):
    SESSION_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(SESSION_FILE.parent, 0o700)
    old = os.umask(0o077)
    try:
        SESSION_FILE.write_text(json.dumps(value, ensure_ascii=False) + '\n')
        os.chmod(SESSION_FILE, 0o600)
    finally:
        os.umask(old)


def _api(path, method='GET', payload=None, auth=True, timeout=25):
    if not path.startswith('/api/') or '..' in path or '//' in path:
        raise RuntimeError('Ruta de API no permitida')
    headers = {'Accept': 'application/json'}
    if auth:
        token = _session().get('token')
        if not token:
            raise RuntimeError('No hay sesión: ejecuta lab login')
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with OPENER.open(Request(API_ROOT + path, data=data, headers=headers, method=method), timeout=timeout) as r:
            raw, code = r.read(2 * 1024 * 1024), r.status
    except HTTPError as e:
        raw, code = e.read(128 * 1024), e.code
    except (URLError, TimeoutError) as e:
        raise RuntimeError('Academy no está disponible; revisa docker compose ps en el anfitrión') from e
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw.decode(errors='replace')
    return code, value


def _print(value):
    print(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))


def _auth(command):
    user = input('Usuario del portal: ').strip()
    password = getpass.getpass('Contraseña: ')
    if command == 'register' and getpass.getpass('Repite la contraseña: ') != password:
        raise RuntimeError('Las contraseñas no coinciden')
    code, value = _api('/api/auth/' + command, 'POST', {'username': user, 'password': password}, auth=False)
    if code >= 400:
        _print(value)
        return 1
    if not isinstance(value, dict) or not isinstance(value.get('token'), str):
        raise RuntimeError('Respuesta de autenticación inválida')
    _save_session({'token': value['token'], 'username': user})
    print(f'Sesión individual iniciada para {user}. Al terminar usa lab logout.')
    return 0


def _pairs(items, label, encoded=False):
    result = {}
    for item in items:
        if '=' not in item:
            raise RuntimeError(label + ' requiere clave=valor')
        key, value = item.split('=', 1)
        if not key or any(ord(c) < 32 for c in key):
            raise RuntimeError('Clave inválida')
        if label == '--header' and any(ord(c) < 32 for c in value):
            raise RuntimeError('Un header no puede contener caracteres de control')
        result[key] = unquote(value) if encoded else value
    return result


def _request(args):
    params = _pairs(args.param, '--param')
    params.update(_pairs(args.param_encoded, '--param-encoded', encoded=True))
    body = args.body
    if args.body_file:
        if body is not None:
            raise RuntimeError('Usa --body o --body-file, no ambos')
        path = Path(args.body_file).expanduser()
        if not path.is_file() or path.stat().st_size > 16 * 1024:
            raise RuntimeError('Archivo de cuerpo inválido o mayor de 16 KiB')
        body = path.read_text()
    payload = {'mission_id': args.mission, 'request': {
        'method': args.method, 'params': params, 'headers': _pairs(args.header, '--header'),
        'body': body, 'content_type': args.content_type}}
    code, value = _api('/api/attempt', 'POST', payload)
    _print(value)
    if code >= 400:
        return 1
    return 0 if value.get('success') else 3


def _doctor():
    missing = []
    for name in ['curl', 'python3', 'jq', 'openssl', 'nmap', 'sqlmap', 'ldapsearch', 'chromium', 'firefox-esr', 'zaproxy']:
        location = shutil.which(name)
        print(f'{name:12} {location or "NO INSTALADO"}')
        if not location:
            missing.append(name)
    print('Las herramientas se ejecutan dentro de Kali. Solo se autorizan los servicios del laboratorio.')
    return 1 if missing else 0


def build_parser():
    p = argparse.ArgumentParser(prog='lab', description='Taller local VulnerableApp en español')
    sub = p.add_subparsers(dest='command', required=True)
    for name in ['login', 'register', 'logout', 'missions', 'status', 'export', 'doctor']:
        sub.add_parser(name)
    req = sub.add_parser('request', help='Intento con evidencia del runner y puntaje individual')
    req.add_argument('mission')
    req.add_argument('--param', action='append', default=[])
    req.add_argument('--param-encoded', action='append', default=[], help='Valor percent-encoded; permite transportar %00 sin NUL en argv')
    req.add_argument('--header', action='append', default=[])
    req.add_argument('--method', choices=['GET', 'POST', 'PUT'], default='GET')
    req.add_argument('--body')
    req.add_argument('--body-file')
    req.add_argument('--content-type')
    tutor = sub.add_parser('tutor').add_subparsers(dest='tutor_command', required=True)
    msg = tutor.add_parser('msg', help='Pedir explicación sin ejecutar herramientas')
    msg.add_argument('--mission', required=True)
    msg.add_argument('message', nargs='+')
    approve = tutor.add_parser('approve', help='Aprobación explícita de una propuesta mostrada antes')
    approve.add_argument('pending_id')
    return p


def main():
    args = build_parser().parse_args()
    if args.command in {'login', 'register'}:
        return _auth(args.command)
    if args.command == 'logout':
        SESSION_FILE.unlink(missing_ok=True)
        print('Sesión del terminal cerrada. Cierra también la sesión del portal si compartes equipo.')
        return 0
    if args.command == 'doctor':
        return _doctor()
    if args.command == 'request':
        return _request(args)
    if args.command == 'missions':
        code, data = _api('/api/catalog', auth=False)
        if code < 400:
            for m in data.get('missions', []):
                label = f'{m["points"]} XP' if m.get('points') else 'manual / 0 XP'
                print(f'{m["id"]:28} {label:15} {m["title"]}')
            return 0
    elif args.command in {'status', 'export'}:
        code, data = _api('/api/me' if args.command == 'status' else '/api/export')
    elif args.tutor_command == 'msg':
        code, data = _api('/api/tutor', 'POST', {
            'mission_id': args.mission, 'message': ' '.join(args.message), 'allow_tools': False}, timeout=180)
    else:
        code, data = _api('/api/tutor/approve', 'POST', {'pending_id': args.pending_id})
    _print(data)
    return 1 if code >= 400 else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError) as error:
        print('lab: ' + str(error), file=sys.stderr)
        sys.exit(2)
