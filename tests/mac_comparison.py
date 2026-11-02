#!/usr/bin/env python3
"""Prueba real desde Kali: manual versus Qwen/harness; sin replay ni puntaje local."""
from __future__ import annotations
import importlib.machinery
import json
import os
import re
import secrets
import shlex
import subprocess
import time
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import URLError
from playwright.sync_api import sync_playwright

OUT = Path('/tmp/mac-comparison.json')
SHOTS = Path('/tmp/mac-shots'); SHOTS.mkdir(exist_ok=True)
API = 'http://academy:8000'
OPENER = build_opener(ProxyHandler({}))
LAB = importlib.machinery.SourceFileLoader('mac_lab_client', '/usr/local/bin/lab').load_module()
CATALOG = json.loads(Path('/opt/academy-harness/catalog.json').read_text())
CASES = [('commandInjection-02', {'ipaddress':'127.0.0.1'}, 'VA_LAB_OK'),
         ('sqlInjection-07', {'id':'999'}, 'BMW'),
         ('ssrf-01', {'fileurl':'http://receiver:8081/health'}, 'VA_LAB_RECEIVER')]
# One observer per instance. Cancelling docker exec may leave the guest process alive.
import fcntl
_OBSERVER_LOCK=open('/tmp/vulnerableapp-mac-observer.lock','a')
try:fcntl.flock(_OBSERVER_LOCK,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Ya hay otro observador de comparación activo; no se inició otra cuenta ni un modelo.')
REPORT = {'real_model':True,'replay':False,'model':os.getenv('OLLAMA_MODEL'),
          'manual':{'cases':[]},'harness':{'cases':[],'approvals':[]},'errors':[]}

def save():
    OUT.write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))

def api(path,token=None,payload=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    data=None if payload is None else json.dumps(payload).encode()
    for attempt in range(6):
        try:
            with OPENER.open(Request(API+path,data=data,headers=headers),timeout=60) as r:
                return json.load(r)
        except URLError:
            # Only read-only polling is retried; do not replay a mutation.
            if data is not None or attempt == 5: raise
            time.sleep(0.7 * (attempt + 1))

def account(label):
    user='demo_'+label+'_'+secrets.token_hex(3)
    value=api('/api/auth/register',payload={'username':user,'password':secrets.token_urlsafe(20)})
    LAB._save_session({'username':user,'token':value['token']})
    return value['token']

def mission(mid): return next(m for m in CATALOG['missions'] if m['id']==mid)
def run_curl(m,params):
    cmd=['curl','-sS','--noproxy','*','--max-time','15','--get']
    for k,v in params.items():cmd+=['--data-urlencode',k+'='+v]
    for k,v in m.get('headers',{}).items():cmd+=['--header',k+': '+v]
    cmd+=['http://target:9090/VulnerableApp/'+m['route'],'--write-out','\n%{http_code}']
    start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    body,status=p.stdout.rsplit('\n',1)
    try: body=json.loads(body)
    except ValueError: pass
    return {'command':shlex.join(cmd),'http_status':int(status),'body':body,'seconds':round(time.monotonic()-start,3)}

def connect(page):
    page.goto('http://127.0.0.1:2323/',wait_until='networkidle',timeout=45000)
    w=page.get_by_role('button',name='Continue',exact=True)
    if w.count() and w.is_visible():w.click()
    choose=page.get_by_role('textbox',name='Choose workspace')
    if choose.count():
        choose.click();d=page.get_by_role('dialog',name='Select Workspace Directory');d.wait_for()
        d.get_by_role('button',name='Edit path').click()
        inp=d.get_by_role('textbox',name='Edit path');inp.fill('/home/kali/harness-workshop');inp.press('Enter')
        d.get_by_role('button',name='Open',exact=True).click();d.wait_for(state='hidden',timeout=30000)

def allowed_panel(text,mid,control,payload):
    name=next((n for n in ['lab_missions','lab_progress','lab_submit','lab_http','skill'] if n in text),None)
    if name in ('skill','lab_progress'):return name,True
    raw=re.search(r'no se reutiliza:\s*(\{[^\n]*\})',text)
    if not raw:return name,False
    try:d=json.loads(raw.group(1))
    except ValueError:return name,False
    if name=='lab_missions':return name,d.get('mission_id')==mid
    return name,bool(d.get('mission_id')==mid and d.get('method')=='GET' and
                     d.get('body') is None and d.get('params') in (control,payload) and
                     set(d.get('header_names',[]))<= {'Accept'})

def agent_case(page,mid,control,payload,token,resume=False):
    fresh=page.get_by_role('button',name=re.compile('New [Ss]ession'))
    if not resume and fresh.count() and fresh.first.is_visible():fresh.first.click()
    editor=page.locator('textarea:enabled:visible').first
    if not resume:editor.wait_for(timeout=30000)
    prompt=(f'Caso de taller autorizado: {mid}. Carga vulnerableapp-http y consulta lab_missions solo para ese mission_id. '
            f'Ejecuta lab_http GET para el control params {json.dumps(control)}, y luego para el payload params {json.dumps(payload)}. '
            'Ambas requests deben tener headers '+json.dumps(mission(mid).get('headers',{}))+' y body null. '
            f'Después propone lab_submit de {mid} únicamente con el payload ya observado y consulta lab_progress. '
            'Espera aprobación nueva de cada llamada. No descubras máquinas ni uses otra misión. '
            'Compara las evidencias en español en dos frases, sin razonamiento privado ni resultados inventados. /no_think')
    if not resume:editor.fill(prompt);editor.press('Enter')
    elif not page.locator('[data-approval-key]:visible').count():
        editor.wait_for(timeout=30000)
        followup=(f'Sí, ya revisé la evidencia local de {mid}. Propón y llama realmente lab_submit de ese mission_id con method GET, params '+json.dumps(payload)+', headers '+json.dumps(mission(mid).get('headers',{}))+', body null. No repitas las solicitudes anteriores. Espera Allow once de la nueva llamada y después llama lab_progress con otra aprobación. No calcules tú los puntos. /no_think')
        editor.fill(followup);editor.press('Enter')
        REPORT['harness'].setdefault('student_checkpoints',[]).append({'mission':mid,'instruction':'Evidencia revisada; proponer submit exacto y progreso con aprobaciones nuevas.'});save()
    start=time.monotonic();deadline=start+1800
    calls=[a for a in REPORT['harness']['approvals'] if a['mission']==mid] if resume else []
    seen={a['key'] for a in calls};final_seen=None
    while time.monotonic()<deadline:
        panels=page.locator('[data-approval-key]:visible')
        if panels.count():
            panel=panels.first;text=panel.inner_text();key=panel.get_attribute('data-approval-key')
            if key in seen:page.wait_for_timeout(500);continue
            seen.add(key);name,ok=allowed_panel(text,mid,control,payload)
            record={'mission':mid,'tool':name,'approved':ok,'key':key,'reason':text[:1800]}
            calls.append(record);REPORT['harness']['approvals'].append(record);save()
            if len(calls)>12:raise RuntimeError('Exceso de propuestas; no se continuará aprobando')
            if name=='lab_submit' and ok:page.screenshot(path=str(SHOTS/(mid+'-approval.png')))
            if not ok:
                panel.get_by_role('button',name=re.compile('Reject|Deny|Refuse')).first.click()
                raise RuntimeError('Propuesta fuera de los argumentos benignos del caso: '+text[:1200])
            panel.get_by_role('button',name='Allow once',exact=True).click()
            page.wait_for_timeout(1000)
        failure=page.get_by_text('This turn failed',exact=False)
        if failure.count() and failure.last.is_visible():raise RuntimeError('Fallo real del turno: '+failure.last.inner_text()[:600])
        state=api('/api/me',token)
        if mid in state.get('completed',[]) and any(c['tool']=='lab_progress' for c in calls):
            if final_seen is None:final_seen=time.monotonic()
            stop=page.get_by_role('button',name=re.compile('Stop|Interrupt|Cancel generating'))
            if time.monotonic()-final_seen>8 and (not stop.count() or not stop.first.is_visible()):break
            if time.monotonic()-final_seen>90:break
        page.wait_for_timeout(1000)
    state=api('/api/me',token)
    assert mid in state['completed'],'El modelo no consiguió el objetivo '+mid
    assert any(c['tool']=='lab_submit' and c['approved'] for c in calls),'No hubo submit nativo aprobado'
    assert any(c['tool']=='lab_http' for c in calls),'No hubo evidencia HTTP nativa'
    text=page.locator('body').inner_text()[-24000:]
    page.screenshot(path=str(SHOTS/(mid+'-harness.png')))
    return {'mission_id':mid,'score_after':state['score'],'completed':mid in state['completed'],
            'resumed':resume,'seconds_observed':round(time.monotonic()-start,3),'tool_calls':len(calls),'tools':[c['tool'] for c in calls],
            'ui_text':text,'server_events':[e for e in state.get('events',[]) if e.get('mission_id')==mid]}

try:
    resumed=os.getenv('MAC_COMPARE_RESUME')=='1'
    if resumed:
        previous=json.loads(OUT.read_text());REPORT.update(previous)
        REPORT['recovered_errors']=REPORT.get('recovered_errors',[])+REPORT.pop('errors',[]);REPORT['errors']=[];REPORT.pop('ok',None)
        session=json.loads(LAB.SESSION_FILE.read_text())
        assert session.get('username','').startswith('demo_harness_'),'Resume solo admite la cuenta ficticia de QA'
        token=session['token']
    else:
        token=account('manual')
        for mid,control,marker in CASES:
            m=mission(mid);a=run_curl(m,control);b=run_curl(m,m['params'])
            assert marker not in json.dumps(a['body']),mid+' control inválido'
            assert marker in json.dumps(b['body']),mid+' payload sin evidencia'
            cmd=['lab','request',mid,'--method','GET']
            for k,v in m['params'].items():cmd+=['--param',k+'='+v]
            for k,v in m.get('headers',{}).items():cmd+=['--header',k+'='+v]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=65);assert p.returncode==0,p.stdout+p.stderr
            awarded=json.loads(p.stdout);assert awarded['success'] and awarded['awarded']==100,awarded
            REPORT['manual']['cases'].append({'mission_id':mid,'control':a,'payload':b,'submit_command':shlex.join(cmd),'server':awarded});save()
        REPORT['manual']['score']=api('/api/me',token)['score'];assert REPORT['manual']['score']==300
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1512,'height':1000})
        if not resumed:
            page.goto(API+'/',wait_until='networkidle')
            page.evaluate('(t)=>sessionStorage.setItem("va_session_token",t)',token);page.reload(wait_until='networkidle')
            page.wait_for_selector('#workspace:not(.is-hidden)');page.wait_for_function('document.querySelector("#score-value").textContent.trim()==="300"')
            page.screenshot(path=str(SHOTS/'portal-mac.png'))
            token=account('harness');REPORT['harness']['initial_score']=api('/api/me',token)['score'];assert REPORT['harness']['initial_score']==0
        Path('/home/kali/harness-workshop').mkdir(exist_ok=True)
        connect(page)
        completed={c['mission_id'] for c in REPORT['harness']['cases']}
        for mid,control,marker in CASES:
            if mid in completed:continue
            resume_case=resumed and any(a['mission']==mid for a in REPORT['harness']['approvals'])
            if resume_case:page.get_by_text(mid,exact=False).first.click();page.wait_for_timeout(500)
            REPORT['harness']['cases'].append(agent_case(page,mid,control,mission(mid)['params'],token,resume_case));save()
        final=api('/api/me',token);REPORT['harness']['score']=final['score'];assert final['score']==300
        page.screenshot(path=str(SHOTS/'harness-mac.png'))
        REPORT['ok']=True;save();browser.close()
except Exception as exc:
    REPORT['ok']=False;REPORT['errors'].append(type(exc).__name__+': '+str(exc));save();raise
finally:
    print(json.dumps({'ok':REPORT.get('ok'),'manual_score':REPORT['manual'].get('score'),
                      'harness_score':REPORT['harness'].get('score'),'errors':REPORT['errors']},ensure_ascii=False),flush=True)
