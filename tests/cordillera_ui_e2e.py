#!/usr/bin/env python3
"""Real local UI checks. Run only inside Kali; uses a new fictitious account."""
from pathlib import Path
import json, secrets
from playwright.sync_api import sync_playwright

OUT=Path('/tmp/cordillera-ui'); OUT.mkdir(exist_ok=True)
report={'browser':'Chromium inside Kali','errors':[],'responsive':[],'mission':'commandInjection-02'}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
 page=b.new_page(viewport={'width':1440,'height':1000},locale='es-CL')
 page.on('pageerror',lambda e:report['errors'].append(str(e)))
 try:
  page.goto('http://gateway:8080/?revision=cordillera-ui-test',wait_until='domcontentloaded')
  page.get_by_role('tab',name='Crear cuenta',exact=True).click()
  page.get_by_label('Nuevo usuario',exact=True).fill('mc_qa_'+secrets.token_hex(6))
  page.locator('#register-panel').get_by_label('Contraseña',exact=True).fill(secrets.token_urlsafe(24))
  page.get_by_role('button',name='Registrar y entrar',exact=True).click()
  page.get_by_role('button',name='Comenzar taller',exact=True).wait_for(timeout=20000)
  page.locator('#score-value').get_by_text('0',exact=True).wait_for()
  page.screenshot(path=str(OUT/'academy-inicio.png'))
  page.get_by_role('button',name='Comenzar taller',exact=True).click()
  page.wait_for_url('**#mission=commandInjection-02')
  assert 'marcador' in page.locator('#mission-title').inner_text()
  assert page.get_by_role('region',name='Empezar aquí',exact=True).get_by_role('link',name='Abrir tienda vía Kali ↗',exact=True).get_attribute('href').startswith('http://gateway:8080/kali/vnc.html?')
  assert page.locator('#kali-frame').get_attribute('src')=='about:blank'
  page.get_by_role('button',name='Cargar control (no envía)',exact=True).click()
  page.get_by_role('button',name='Enviar mi prueba al laboratorio',exact=True).click()
  page.locator('#evidence-state').get_by_text('EVALUADA / REVISAR',exact=True).wait_for(timeout=45000)
  assert page.locator('#score-value').inner_text()=='0'
  page.get_by_role('button',name='Cargar marcador benigno (no envía)',exact=True).click()
  page.get_by_role('button',name='Enviar mi prueba al laboratorio',exact=True).click()
  page.locator('#evidence-state').get_by_text('VERIFICACIÓN POSITIVA',exact=True).wait_for(timeout=45000)
  page.locator('#score-value').get_by_text('100',exact=True).wait_for(timeout=15000)
  assert 'VA_LAB_OK' in page.locator('#evidence-body').inner_text()
  page.get_by_role('button',name='Enviar mi prueba al laboratorio',exact=True).click()
  page.get_by_role('button',name='Enviar mi prueba al laboratorio',exact=True).wait_for(state='visible')
  report['manual_score']=100;report['control_no_xp']=True
  for w in (390,768,1200,1440,1512):
   page.set_viewport_size({'width':w,'height':1000});page.wait_for_timeout(100)
   overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
   report['responsive'].append({'page':'academy','width':w,'overflow':overflow});assert not overflow
  page.set_viewport_size({'width':1440,'height':1000})
  page.goto('http://target:9090/VulnerableApp/mercado/',wait_until='networkidle')
  page.get_by_role('heading',name='Equipamiento con historia de campo.',exact=False).wait_for(timeout=15000)
  page.screenshot(path=str(OUT/'mercado-cordillera.png'))
  assert page.locator('#featured-products .product-card').count()==3
  assert '$39.990' in page.locator('#featured-products').inner_text()
  catalog=page.request.get('http://target:9090/VulnerableApp/mercado/catalog.json').json()
  report['families']=len(catalog['families']);report['missions']=len(catalog['missions'])
  assert report['families']==20 and report['missions']==189
  page.get_by_role('navigation',name='Navegación principal').get_by_role('link',name='Retos del taller',exact=False).click()
  page.get_by_label('Área del taller',exact=True).select_option('commandInjection')
  page.get_by_label('Nivel / misión exacta',exact=True).select_option('commandInjection-02')
  page.locator('#mission-detail').get_by_role('heading',name='LEVEL_1 — marcador seguro de ejecución de la shell',exact=True).wait_for()
  assert page.locator('#mission-academy-link').get_attribute('href')=='http://gateway:8080/#mission=commandInjection-02'
  assert page.locator('.row-value').input_value()=='127.0.0.1|printf VA_LAB_OK'
  page.get_by_label('Valor de parámetro',exact=True).fill('127.0.0.1')
  page.locator('#confirm-practice').check()
  page.get_by_role('button',name='Enviar control al target',exact=True).click()
  page.locator('#response-panel').wait_for(state='visible',timeout=20000)
  control=page.locator('#response-panel pre').inner_text();assert 'VA_LAB_OK' not in control
  page.get_by_label('Valor de parámetro',exact=True).fill('127.0.0.1|printf VA_LAB_OK')
  page.get_by_role('button',name='Enviar control al target',exact=True).click()
  page.wait_for_function("document.querySelector('#response-panel pre')?.textContent.includes('VA_LAB_OK')",timeout=20000)
  report['store_real_endpoint']=True
  page.screenshot(path=str(OUT/'mercado-reto.png'),full_page=True)
  for w in (390,768,1200,1440,1512):
   page.set_viewport_size({'width':w,'height':1000});page.wait_for_timeout(100)
   overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
   report['responsive'].append({'page':'mercado','width':w,'overflow':overflow});assert not overflow
  page.set_viewport_size({'width':1440,'height':1000})
  page.get_by_role('navigation',name='Navegación principal').get_by_role('link',name='Backoffice pedagógico',exact=True).click()
  page.locator('#page-admin').wait_for(state='visible')
  report['admin']=True
  page.goto('http://target:9090/VulnerableApp/original/',wait_until='networkidle')
  assert 'VulnerableApp' in page.title() or 'Vulnerable App' in page.title()
  report['original_available']=True
  assert not report['errors'],report['errors'];report['ok']=True
 except Exception as exc:
  report['ok']=False;report['error']=type(exc).__name__+': '+str(exc)
  page.screenshot(path=str(OUT/'failure.png'),full_page=True)
  raise
 finally:
  (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));b.close()
print(json.dumps(report,ensure_ascii=False))
