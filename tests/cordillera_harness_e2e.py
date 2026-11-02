#!/usr/bin/env python3
"""Prueba Cordillera: Qwen real, aprobación única, soporte/printf y XP del servidor.
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
        prompt = ('Laboratorio Docker local autorizado. Carga exactamente vulnerableapp-evidence con skill. '
                  'La cuenta ya inició lab login en la terminal. El objetivo y el receptor ya están identificados: no es necesario descubrimiento. '
                  'Consulta primero lab_missions para el único ID commandInjection-02. Después invoca lab_submit con este JSON exacto: '
                  '{"mission_id":"commandInjection-02","request":{"method":"GET","params":{"ipaddress":"127.0.0.1|printf VA_LAB_OK"},"headers":{},"body":null}}. '
                  'Invoca las funciones para crear sus paneles de aprobación; espera la aprobación de cada panel. '
                  'No pidas credenciales. Tras el resultado, invoca lab_progress una sola vez y espera su aprobación. '
                  'Después resume el éxito y XP reales de Academy, sin más llamadas. No uses otras herramientas. /no_think')
        editor.fill(prompt)
        editor.press('Enter')
        deadline = time.monotonic() + 900
        submit_seen = False
        progress_seen = False
        while time.monotonic() < deadline:
            panels = page.locator('[data-approval-key]')
            if panels.count() and panels.first.is_visible():
                panel = panels.first
                text = panel.inner_text()
                key = panel.get_attribute('data-approval-key')
                if len(report['approvals']) >= 4:
                    raise RuntimeError('No se aprobarán más de cuatro llamadas previstas')
                if 'lab_discover' in text or 'lab_http' in text:
                    # This QA run tests scoring, not discovery or probing. A
                    # model-proposed intermediate operation must not run merely
                    # because it is one of the harness's allowlisted tools.
                    report['approvals'].append({'key': key, 'tool': 'unnecessary-probe', 'approved': False})
                    panel.get_by_role('button', name='Reject', exact=True).click()
                    print('REJECTED unnecessary probe', flush=True)
                    page.wait_for_timeout(750)
                    continue
                if not any(name in text for name in ('skill', 'lab_missions', 'lab_submit', 'lab_progress')):
                    raise RuntimeError('El test no aprobará otra herramienta: ' + text[:150])
                if 'lab_missions' in text:
                    summary = re.search(r'no se reutiliza:\s*(\{[^\n]*\})', text)
                    assert summary, 'Sin argumentos de catálogo visibles'
                    assert json.loads(summary.group(1)) == {'mission_id': 'commandInjection-02'}
                if 'lab_progress' in text:
                    summary = re.search(r'no se reutiliza:\s*(\{[^\n]*\})', text)
                    assert summary, 'Sin argumentos de progreso visibles'
                    args = json.loads(summary.group(1))
                    assert set(args).issubset({'session'}), args.keys()
                    progress_seen = True
                if 'lab_submit' in text:
                    summary = re.search(r'no se reutiliza:\s*(\{[^\n]*\})', text)
                    assert summary, 'No se pudo inspeccionar el argumento de la aprobación'
                    args = json.loads(summary.group(1))
                    assert args.get('mission_id') == 'commandInjection-02' and args.get('method') == 'GET'
                    assert args.get('params') == {'ipaddress':'127.0.0.1|printf VA_LAB_OK'}
                submit_seen = submit_seen or 'lab_submit' in text
                tool = 'lab_submit' if 'lab_submit' in text else ('lab_missions' if 'lab_missions' in text else ('lab_progress' if 'lab_progress' in text else 'skill'))
                report['approvals'].append({'key': key, 'tool': tool, 'approved': True})
                page.screenshot(path='/tmp/cordillera-harness-approval-%d.png' % len(report['approvals']), full_page=True)
                panel.get_by_role('button', name='Allow once', exact=True).click()
                print('APPROVED', report['approvals'][-1]['tool'], flush=True)
                page.wait_for_timeout(1000)
            if submit_seen and progress_seen:
                current = api('/api/me', token=token)
                if current['score'] == 100:
                    assert 'commandInjection-02' in current.get('completed', []), 'Los XP no corresponden a la misión prevista'
                    report['score'] = current['score']
                    report['completed'] = current.get('completed', [])
                    report['success'] = True
                    # Give the UI time to commit the tool result; do not need
                    # another inference to establish authoritative server XP.
                    page.wait_for_timeout(2500)
                    page.screenshot(path='/tmp/cordillera-harness-success.png', full_page=True)
                    report['ok'] = True
                    break
                if current['score'] != 0:
                    raise AssertionError('Puntaje distinto al objetivo único previsto')
            failure = page.get_by_text('This turn failed', exact=False)
            if failure.count() and failure.last.is_visible():
                raise RuntimeError('El modelo falló: ' + failure.last.inner_text()[:300])
            page.wait_for_timeout(750)
        else:
            raise TimeoutError('El modelo no logró el objetivo autenticado en el límite de QA')
        assert submit_seen and progress_seen and report.get('score') == 100
        assert len({a['key'] for a in report['approvals']}) == len(report['approvals'])
        assert not report['page_errors'], report['page_errors']
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
