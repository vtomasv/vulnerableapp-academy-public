#!/usr/bin/env python3
"""Verifica el site estático preparado en /tmp/site-preview y guarda capturas reales."""
from pathlib import Path
import json,shutil
from playwright.sync_api import sync_playwright
root=Path('/tmp/site-preview');shots=Path('/tmp/site-shots');shots.mkdir(exist_ok=True)
errors=[];checks=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1512,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto((root/'comparison.html').as_uri(),wait_until='networkidle');page.screenshot(path=str(shots/'comparison-mac.png'));shutil.copyfile(shots/'comparison-mac.png',root/'assets/comparison-mac.png')
 for width,height in [(1512,1000),(768,1024),(390,844)]:
  page.set_viewport_size({'width':width,'height':height});page.goto((root/'index.html').as_uri(),wait_until='networkidle');page.wait_for_timeout(800)
  size=page.evaluate('({w:innerWidth,s:document.documentElement.scrollWidth})');assert size['s']<=size['w']+1,size
  page.locator('img').evaluate_all('(imgs)=>imgs.forEach(i=>i.loading="eager")');page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)',timeout=15000)
  broken=page.locator('img').evaluate_all('(imgs)=>imgs.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)');assert not broken,broken
  anchors=page.locator('a[href^="#"]').evaluate_all('(as)=>as.map(a=>a.getAttribute("href")).filter(h=>h.length>1&&!document.getElementById(h.slice(1)))');assert not anchors,anchors
  if width==1512:
   y=page.locator('.hero-actions').evaluate('(e)=>e.getBoundingClientRect().bottom');assert y<1000,y
   page.screenshot(path=str(shots/'website-desktop.png'))
  if width==390:
   page.locator('.menu-toggle').click();assert page.locator('.menu-toggle').get_attribute('aria-expanded')=='true';page.locator('.menu-toggle').click()
   page.screenshot(path=str(shots/'website-mobile.png'))
  checks.append({'width':width,'no_overflow':True,'assets':True,'anchors':True})
 page.set_viewport_size({'width':1512,'height':1000});page.goto((root/'comparison.html').as_uri(),wait_until='networkidle');page.screenshot(path=str(shots/'comparison-mac.png'))
 assert page.locator('tbody tr').count()==3
 # Re-encode the existing branded SVG for social clients that reject SVG images.
 page.set_viewport_size({'width':1200,'height':630});page.goto((root/'assets/og-image.svg').as_uri(),wait_until='networkidle');page.screenshot(path=str(shots/'og-image.png'))
 b.close()
assert not errors,errors
(shots/'site-validation.json').write_text(json.dumps({'ok':True,'checks':checks,'errors':errors},indent=2)+'\n');print(json.dumps({'ok':True,'checks':checks}))
