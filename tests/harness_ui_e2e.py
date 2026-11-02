#!/usr/bin/env python3
"""Prueba real del harness web desde Chromium dentro de Kali (sin replay)."""
from __future__ import annotations
import json
import os
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('/tmp/harness-ui-e2e.json')
WORKSPACE = Path('/home/kali/harness-workshop')
WORKSPACE.mkdir(exist_ok=True)
report = {'real_model': True, 'replay': False, 'approvals': [], 'page_errors': [], 'turns': []}


def wait_turn(page, limit=180):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        panel = page.locator('[data-approval-key]')
        if panel.count() and panel.first.is_visible():
            return 'approval'
        stop = page.get_by_role('button', name=re.compile(r'Stop|Interrupt|Cancel generating'))
        if not stop.count() or not stop.first.is_visible():
            textarea = page.locator('textarea:enabled').first
            if textarea.count() and textarea.is_enabled():
                time.sleep(1)
                if not page.locator('[data-approval-key]').count():
                    return 'settled'
        page.wait_for_timeout(500)
    raise TimeoutError('El turno no llegó a aprobación ni finalizó')


def send_turn(page, prompt, approve=True, max_calls=4):
    editor = page.locator('textarea:enabled:visible').first
    editor.fill(prompt)
    editor.press('Enter')
    page.wait_for_timeout(1500)
    until = time.monotonic() + 180
    while time.monotonic() < until:
        panel = page.locator('[data-approval-key]')
        if panel.count() and panel.first.is_visible():
            break
        failure = page.get_by_text('This turn failed', exact=False)
        if failure.count() and failure.last.is_visible():
            raise RuntimeError('La UI informó fallo real de inferencia: ' + failure.last.inner_text()[:600])
        page.wait_for_timeout(500)
    else:
        raise TimeoutError('El modelo no produjo una solicitud de aprobación en 180 segundos')
    calls = []
    for _ in range(max_calls):
        state = wait_turn(page)
        if state == 'settled':
            break
        panel = page.locator('[data-approval-key]').first
        text = panel.inner_text()
        key = panel.get_attribute('data-approval-key')
        expected = 'skill' if 'Carga exactamente el skill' in prompt else 'lab_discover'
        if expected not in text:
            raise RuntimeError('La prueba no aprobará una herramienta distinta de ' + expected)
        calls.append({'key': key, 'text': text[:4000], 'approved': approve})
        report['approvals'].append(calls[-1])
        page.screenshot(path=f'/tmp/harness-approval-{len(report["approvals"])}.png', full_page=True)
        button = panel.get_by_role('button', name='Allow once' if approve else 'Reject', exact=True)
        if not button.count() and not approve:
            button = panel.get_by_role('button', name='Deny', exact=True)
        if not button.count() and not approve:
            button = panel.get_by_role('button', name='Refuse', exact=True)
        button.click()
        page.wait_for_timeout(1500)
    else:
        raise RuntimeError('Demasiadas llamadas; no se aprobarán operaciones adicionales')
    report['turns'].append({'prompt': prompt, 'calls': calls, 'text': page.locator('body').inner_text()[-16000:]})
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return calls


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='en-US')
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    try:
        page.goto('http://127.0.0.1:2323/', wait_until='networkidle', timeout=45000)
        page.screenshot(path='/tmp/harness-initial.png', full_page=True)
        print('UI_INITIAL', page.locator('body').inner_text()[:3000], flush=True)
        welcome = page.get_by_role('button', name='Continue', exact=True)
        if welcome.count() and welcome.is_visible():
            welcome.click()
        choose = page.get_by_role('textbox', name='Choose workspace')
        if choose.count():
            choose.click()
            dialog = page.get_by_role('dialog', name='Select Workspace Directory')
            dialog.wait_for(timeout=10000)
            dialog.get_by_role('button', name='Edit path').click()
            path_input = dialog.get_by_role('textbox', name='Edit path')
            path_input.fill(str(WORKSPACE))
            path_input.press('Enter')
            dialog.get_by_role('button', name='Open', exact=True).click()
            dialog.wait_for(state='hidden', timeout=30000)
        page.locator('textarea:enabled:visible').first.wait_for(timeout=30000)
        fresh = page.get_by_role('button', name=re.compile(r'New [Ss]ession'))
        if fresh.count() and fresh.first.is_visible():
            fresh.first.click()
        page.locator('textarea:enabled:visible').first.wait_for(timeout=30000)
        print('UI_READY', page.locator('body').inner_text()[:3000], flush=True)
        resume = os.environ.get('HARNESS_TEST_RESUME_SESSION')
        if resume:
            prior = json.loads(OUT.read_text())
            report.update({k: prior[k] for k in ('approvals', 'turns')})
            report['resumed_session'] = resume
            page.get_by_text(resume, exact=True).first.click()
            page.locator('textarea:enabled:visible').first.wait_for(timeout=30000)
            calls = report['turns'][0]['calls']
        else:
            calls = send_turn(page, 'Estamos en el laboratorio Docker local autorizado. Usa exactamente lab_discover con {"service":"all"}; espera mi aprobación de la herramienta. Después informa los cinco nombres y puertos observados. No uses otras herramientas en este turno. /no_think', True)
        assert calls, 'El modelo no produjo una llamada real que requiera aprobación'
        assert any('lab_discover' in c['text'] for c in calls), 'No apareció lab_discover'
        page.screenshot(path='/tmp/harness-discovery.png', full_page=True)
        print('DISCOVERY_TURN_DONE', flush=True)
        rejected = send_turn(page, 'Haz otra comprobación usando exactamente lab_discover con {"service":"target"}. Espera la nueva aprobación; si la rechazo no vuelvas a intentar ni uses alternativas. /no_think', False, 2)
        assert rejected, 'La segunda llamada no pidió una aprobación nueva'
        assert set(c['key'] for c in calls).isdisjoint(c['key'] for c in rejected), 'Se reutilizó un identificador de aprobación'
        page.screenshot(path='/tmp/harness-rejected.png', full_page=True)
        print('REJECTION_TURN_DONE', flush=True)
        skill_calls = send_turn(page, 'Carga exactamente el skill vulnerableapp-http con la herramienta skill. Espera mi aprobación; luego resume en español su método de comparación sin ejecutar solicitudes HTTP. /no_think', True, 2)
        assert skill_calls and all('skill' in c['text'] for c in skill_calls), 'La carga del skill no solicitó aprobación'
        assert 'vulnerableapp-http' in report['turns'][-1]['text'], 'El skill seleccionado no apareció en el resultado del turno'
        print('SKILL_TURN_DONE', flush=True)
        report['ok'] = True
        assert not report['page_errors'], report['page_errors']
    except Exception as exc:
        report['ok'] = False
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['body'] = page.locator('body').inner_text()[-20000:]
        page.screenshot(path='/tmp/harness-ui-failure.png', full_page=True)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        browser.close()
