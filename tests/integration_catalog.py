#!/usr/bin/env python3
"""Prueba recetas concretas. No ejecuta escáneres ni prueba destinos externos."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
MISSING = object()


def json_path(value, path):
    path = str(path or '').removeprefix('$.').lstrip('/').replace('/', '.')
    for key in path.split('.') if path else []:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return MISSING
        if isinstance(value, list) and key.isdigit():
            try:
                value = value[int(key)]
            except IndexError:
                return MISSING
        elif isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return MISSING
    return value


def check_evidence(c, e):
    kind = c.get('kind')
    statuses = c.get('status', [200, 201, 202, 204, 302])
    if isinstance(statuses, int):
        statuses = [statuses]
    if e.get('exit_code') != 0 or e.get('status') not in statuses:
        return False
    if kind == 'all':
        return all(check_evidence(x, e) for x in c['checks'])
    headers = {k.lower(): v for k, v in e['headers'].items()}
    if kind == 'header':
        return headers.get(c['header'].lower()) == str(c['value'])
    if kind == 'header_contains':
        return str(c['value']).lower() in headers.get(c['header'].lower(), '').lower()
    if kind == 'absent_header':
        return c['header'].lower() not in headers
    if kind == 'browser_dataset':
        return json_path(e.get('browser_dataset', {}), c.get('path')) == c['value']
    value = e['body']
    if kind == 'json' or c.get('path'):
        try:
            value = json_path(json.loads(value), c.get('path'))
        except ValueError:
            return False
        if value is MISSING:
            return False
    if kind == 'json':
        return value == c['value']
    if not isinstance(value, str):
        value = json.dumps(value)
    if kind == 'contains':
        return str(c['value']) in value
    if kind == 'not_contains':
        return str(c['value']) not in value
    return False


def request(base, m, browser=False):
    url = base.rstrip('/') + '/VulnerableApp/' + m['route']
    params = m.get('params') or {}
    headers = m.get('headers') or {}
    if m.get('content_type'):
        headers = {**headers, 'Content-Type': m['content_type']}
    body = m.get('body')
    # Desde Kali, receiver es el nombre DNS correcto del servicio Compose.
    # Solo una ejecución contra un target publicado en localhost necesita la
    # sustitución; 127.0.0.1 dentro del contenedor target no es receiver.
    if urlsplit(base).hostname in {'127.0.0.1', 'localhost'}:
        params = {k: v.replace('http://receiver:8081', 'http://127.0.0.1:8081') if isinstance(v, str) else v
                  for k, v in params.items()}
        if body:
            body = body.replace('http://receiver:8081', 'http://127.0.0.1:8081')
    r = requests.request(m.get('method', 'GET'), url, params=params, headers=headers,
                         data=body, timeout=15, allow_redirects=False)
    e = {'status': r.status_code, 'headers': dict(r.headers), 'body': r.text, 'exit_code': 0}
    if browser:
        from playwright.sync_api import sync_playwright
        full = requests.Request('GET', url, params=params).prepare().url
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                  args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = b.new_page()
            origin = urlsplit(base)
            def restrict(route):
                dest = urlsplit(route.request.url)
                if (dest.scheme, dest.hostname, dest.port) == (origin.scheme, origin.hostname, origin.port):
                    route.continue_()
                else:
                    route.abort()
            page.route('**/*', restrict)
            page.goto(full, wait_until='domcontentloaded', timeout=15000)
            page.wait_for_timeout(1000)
            e['browser_dataset'] = page.evaluate('({vaLab: document.body.dataset.vaLab || null})')
            b.close()
    return e


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:9090')
    parser.add_argument('--output', default=str(ROOT / 'tests/catalog-results.json'))
    parser.add_argument('--ids', default='')
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {'127.0.0.1', 'localhost', 'target'}:
        parser.error('Solo se permite localhost o el servicio target del laboratorio.')
    catalog = json.loads((ROOT / 'academy/data/catalog.json').read_text())
    rows = []
    selected = args.ids.split(',') if args.ids else None
    for m in catalog['missions']:
        if not m['points'] or (selected and m['id'] not in selected):
            continue
        if m['family'] == 'cryptographicFailures' and m['id'] != 'cryptographicFailures-10':
            continue  # Las semillas aleatorias requieren que el alumno resuelva el reto.
        try:
            for before in m.get('before', []):
                request(args.base_url, before)
            attack = request(args.base_url, m, m.get('tool') == 'browser_probe')
            e = request(args.base_url, m['probe'], m.get('tool') == 'browser_probe') if m.get('probe') else attack
            ok = check_evidence(m['check'], e)
            if m.get('baseline'):
                ctrl = request(args.base_url, m['baseline'])
                ok = ok and check_evidence(m['baseline']['check'], ctrl)
            rows.append({'id': m['id'], 'pass': ok, 'status': e['status'],
                         'body_sample': e['body'][:700], 'headers': e['headers'],
                         'browser_dataset': e.get('browser_dataset')})
            print(m['id'], 'OK' if ok else 'NO', e['status'], flush=True)
        except Exception as exc:
            rows.append({'id': m['id'], 'pass': False, 'error': str(exc)[:300]})
            print(m['id'], 'ERROR', str(exc)[:100], flush=True)
    Path(args.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    print(f'{sum(x["pass"] for x in rows)}/{len(rows)} recetas cumplieron su criterio.')
    return 0 if rows and all(x['pass'] for x in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
