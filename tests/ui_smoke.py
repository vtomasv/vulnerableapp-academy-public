#!/usr/bin/env python3
import json
import secrets
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/images'
OUT.mkdir(exist_ok=True, parents=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                args=['--no-sandbox', '--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1512, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8000/', wait_until='networkidle')
    page.click('[data-auth-tab="register"]')
    page.fill('#register-username', 'visual_' + secrets.token_hex(4))
    page.fill('#register-password', secrets.token_urlsafe(12))
    page.click('#register-panel button[type="submit"]')
    page.wait_for_selector('#workspace:not(.is-hidden)', timeout=15000)
    page.wait_for_timeout(1000)
    page.click('[data-mission-id="authentication-01"]')
    session = requests.Session(); session.trust_env = False
    catalog = session.get('http://127.0.0.1:8000/api/catalog').json()
    mission = next(m for m in catalog['missions'] if m['id'] == 'authentication-01')
    request = {k: mission.get(k) for k in ['method', 'params', 'headers', 'body', 'content_type']}
    page.fill('.request-textarea', json.dumps(request))
    page.click('.request-editor button')
    page.wait_for_function('document.querySelector("#score-value").textContent.trim() === "100"', timeout=15000)
    page.wait_for_timeout(200)
    page.screenshot(path=str(OUT / 'portal-desktop.png'), full_page=True)
    assert '[object Object]' not in page.locator('body').inner_text()
    assert page.locator('#family-count').inner_text().strip() == '20'
    page.set_viewport_size({'width': 390, 'height': 844})
    page.screenshot(path=str(OUT / 'portal-mobile.png'), full_page=True)
    dimensions = page.evaluate('({width: innerWidth, scroll: document.documentElement.scrollWidth})')
    assert dimensions['scroll'] <= dimensions['width'] + 1, dimensions
    page.click('#logout-button')
    assert page.locator('#workspace').evaluate('e=>e.classList.contains("is-hidden")')
    assert not errors, errors
    (ROOT / 'tests/ui-results.json').write_text(json.dumps({'pass': True, 'errors': errors,
                                                           'mobile': dimensions}, indent=2)+'\n')
    browser.close()
print('UI: registro, intento real con 100 XP, catálogo, criterio JSON, logout, escritorio y móvil sin overflow ni errores JS.')
