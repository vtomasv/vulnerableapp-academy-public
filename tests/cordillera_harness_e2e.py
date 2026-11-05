#!/usr/bin/env python3
"""Prueba Cordillera: Qwen real, aprobación única y XP del servidor.
Ejecutar dentro de Kali; conserva la sesión privada previa del CLI.
"""
from __future__ import annotations
import importlib.machinery
import importlib.util
import json
import re
import secrets
import time
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener
from playwright.sync_api import sync_playwright

OUT = Path('/tmp/cordillera-harness-e2e.json')
WORKSPACE = Path('/home/kali/qa-cordillera-' + secrets.token_hex(4))
WORKSPACE.mkdir(exist_ok=True)
report = {'real_model': True, 'replay': False, 'approvals': [], 'page_errors': [], 'mission_id':'commandInjection-02'}
opener = build_opener(ProxyHandler({}))

def api(path, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = None if payload is None else json.dumps(payload).encode()
    with opener.open(Request('http://academy:8000' + path, data=body, headers=headers), timeout=20) as r:
        return json.load(r)

# These credentials stay in memory and the normal private CLI session only.
account = api('/api/auth/register', {'username': 'va_model_' + secrets.token_hex(8), 'password': secrets.token_urlsafe(24)})
token = account['token']
loader = importlib.machinery.SourceFileLoader('va_score_lab_client', '/usr/local/bin/lab')
spec = importlib.util.spec_from_file_location(loader.name, '/usr/local/bin/lab', loader=loader)
client = importlib.util.module_from_spec(spec)
loader.exec_module(client)
previous_session = client.SESSION_FILE.read_bytes() if client.SESSION_FILE.exists() else None
client._save_session({'token': token, 'username': account['user']['username']})
assert api('/api/me', token=token)['score'] == 0

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='en-US')
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    try:
        page.goto('http://127.0.0.1:2323/', wait_until='networkidle', timeout=45000)
        welcome = page.get_by_role('button', name='Continue', exact=True)
        if welcome.count() and welcome.first.is_visible():
            welcome.first.click()
        choose = page.get_by_role('textbox', name='Choose workspace')
        if choose.count():
            choose.click()
            dialog = page.get_by_role('dialog', name='Select Workspace Directory')
            dialog.wait_for(timeout=10000)
            dialog.get_by_role('button', name='Edit path').click()
            edit = dialog.get_by_role('textbox', name='Edit path')
            edit.fill(str(WORKSPACE))
            edit.press('Enter')
            dialog.get_by_role('button', name='Open', exact=True).click()
            dialog.wait_for(state='hidden', timeout=30000)
        editor = page.locator('textarea:enabled:visible').first
        editor.wait_for(timeout=30000)
        request = {
            'mission_id': 'commandInjection-02',
            'request': {'method': 'GET', 'params': {'ipaddress': '127.0.0.1|printf VA_LAB_OK'},
                        'headers': {}, 'body': None, 'content_type': None},
        }
        prompt = (
            'Ya revisé el control y comprobé VA_LAB_OK en el target local. '
            'Invoca lab_submit una sola vez con estos argumentos y espera el panel de aprobación: '
            + json.dumps(request, ensure_ascii=False)
        )
        editor.fill(prompt)
        editor.press('Enter')
        panel = page.locator('[data-approval-key]').first
        panel.wait_for(timeout=180000)
        approval = panel.inner_text()
        assert 'lab_submit' in approval, approval[:300]
        summary = re.search(r'no se reutiliza:\s*(\{[^\n]*\})', approval)
        assert summary, 'No se pudo inspeccionar la aprobación'
        args = json.loads(summary.group(1))
        assert args['mission_id'] == request['mission_id'] and args['method'] == 'GET'
        assert args['params'] == request['request']['params']
        assert api('/api/me', token=token)['score'] == 0
        report['approvals'].append({'key': panel.get_attribute('data-approval-key'),
                                    'tool': 'lab_submit', 'approved': True})
        panel.get_by_role('button', name='Allow once', exact=True).click()
        print('APPROVED lab_submit', flush=True)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            progress = api('/api/me', token=token)
            if progress['score'] == 100:
                assert request['mission_id'] in progress['completed']
                event = next(item for item in progress['events'] if item['mission_id'] == request['mission_id'] and item['success'])
                observed = json.loads(event['evidence']['body'])
                assert observed['content'] == 'VA_LAB_OK' and observed['isValid'] is True
                break
            page.wait_for_timeout(750)
        else:
            raise TimeoutError('Academy no registró los XP del intento aprobado')
        assert not report['page_errors'], report['page_errors']
        report.update(score=progress['score'], completed=progress['completed'], success=True, ok=True)
        print('MODEL_SCORE_SUCCESS 100', flush=True)
    except Exception as exc:
        report['ok'] = False
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        page.screenshot(path='/tmp/cordillera-harness-failure.png', full_page=True)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        browser.close()
        if previous_session is None:
            client.SESSION_FILE.unlink(missing_ok=True)
        else:
            client.SESSION_FILE.write_bytes(previous_session)
            client.SESSION_FILE.chmod(0o600)
