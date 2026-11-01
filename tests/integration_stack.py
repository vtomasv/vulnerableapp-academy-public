#!/usr/bin/env python3
"""Integra API, runner auténtico y target; no requiere Ollama para puntuar."""
import argparse
import json
import secrets
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--api', default='http://127.0.0.1:8000')
    p.add_argument('--ids', default='')
    p.add_argument('--output', default=str(ROOT / 'tests/stack-results.json'))
    a = p.parse_args()
    if a.api not in {'http://127.0.0.1:8000', 'http://academy:8000'}:
        p.error('La prueba se limita al API local del laboratorio.')
    s = requests.Session(); s.trust_env = False
    user = s.post(a.api + '/api/auth/register', json={'username': 'qa_' + secrets.token_hex(5),
                                                  'password': secrets.token_urlsafe(15)}).json()
    assert 'token' in user, user
    headers = {'Authorization': 'Bearer ' + user['token']}
    catalog = s.get(a.api + '/api/catalog').json()
    selected = a.ids.split(',') if a.ids else None
    rows = []
    for m in catalog['missions']:
        if not m['points'] or (selected and m['id'] not in selected):
            continue
        if m['family'] == 'cryptographicFailures' and m['id'] != 'cryptographicFailures-10':
            continue
        payload = {'mission_id': m['id'], 'request': {k: m.get(k) for k in
                   ['method', 'params', 'headers', 'body', 'content_type']}}
        try:
            r = s.post(a.api + '/api/attempt', headers=headers, json=payload, timeout=50)
            data = r.json(); e = data.get('evidence', {})
            row = {'id': m['id'], 'http': r.status_code, 'pass': data.get('success') is True,
                   'awarded': data.get('awarded', 0), 'message': data.get('message', data.get('detail')),
                   'status': e.get('status'), 'body_sample': str(e.get('body', ''))[:600],
                   'dataset': e.get('browser_dataset'), 'headers': e.get('headers')}
        except Exception as exc:
            row = {'id': m['id'], 'pass': False, 'error': str(exc)[:200]}
        rows.append(row)
        print(row['id'], 'OK' if row['pass'] else 'NO', row.get('awarded'), flush=True)
    Path(a.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    good = sum(r['pass'] for r in rows)
    print(f'{good}/{len(rows)} objetivos verificados mediante API→runner→target.')
    return 0 if rows and good == len(rows) else 1

if __name__ == '__main__':
    raise SystemExit(main())
