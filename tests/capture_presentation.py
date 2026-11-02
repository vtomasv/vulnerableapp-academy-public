#!/usr/bin/env python3
"""Capturas de páginas reales/static source dentro de Kali; sin modificar pixels."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

out=Path('/tmp/presentation-shots');out.mkdir(exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':1512,'height':1000})
    page.goto('http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale&path=websockify',wait_until='networkidle')
    page.wait_for_function('document.documentElement.classList.contains("noVNC_connected")',timeout=20000)
    page.wait_for_timeout(4000)
    page.screenshot(path=str(out/'kali-mac.png'))
    site=Path('/tmp/site-preview/index.html')
    if site.exists():
        page.goto(site.as_uri(),wait_until='networkidle')
        page.wait_for_timeout(500)
        page.screenshot(path=str(out/'website-desktop.png'))
        # No capturar una web larga como una imagen ilegible; entregar vistas de viewport.
        page.set_viewport_size({'width':390,'height':844});page.reload(wait_until='networkidle')
        dimensions=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
        assert dimensions['scroll']<=dimensions['width']+1,dimensions
        page.screenshot(path=str(out/'website-mobile.png'))
        (out/'presentation-results.json').write_text(json.dumps({'ok':True,'mobile':dimensions}))
    b.close()
