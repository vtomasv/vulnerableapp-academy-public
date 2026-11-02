#!/usr/bin/env python3
"""Medición técnica real de Qwen en Ollama Docker; no estima resolución de alumnos."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from urllib.request import Request, ProxyHandler, build_opener

BASE = 'http://ollama:11434'
MODEL = os.environ.get('OLLAMA_MODEL', 'huihui_ai/Qwen3.8-abliterated:27b')
THREADS = int(os.environ.get('OLLAMA_NUM_THREADS', '12'))
OUT = Path(os.environ.get('BENCHMARK_OUTPUT', '/tmp/benchmark-qwen27.json'))
OPENER = build_opener(ProxyHandler({}))

def api(path, payload=None, timeout=1800):
    data = None if payload is None else json.dumps(payload).encode()
    return OPENER.open(Request(BASE + path, data=data, headers={'Content-Type': 'application/json'}), timeout=timeout)

def get_json(path, payload=None):
    with api(path, payload) as r:
        return json.load(r)

def trial(label, prompt):
    body = {'model': MODEL, 'stream': True, 'think': False, 'keep_alive': '30m',
            'messages': [{'role':'system','content':'Eres el tutor de un laboratorio Docker aislado. Responde en español. Solo servicios target, receiver, mailpit, academy y ollama. Entrega conclusiones, no razonamiento privado.'},
                         {'role':'user','content':prompt}],
            'options': {'num_ctx':8192, 'num_thread':THREADS, 'num_predict':96, 'temperature':0.1}}
    start = time.perf_counter()
    first = None
    text = []
    final = None
    with api('/api/chat', body) as r:
        for raw in r:
            event = json.loads(raw)
            if 'error' in event:
                raise RuntimeError(event['error'])
            content = event.get('message', {}).get('content', '')
            if content:
                if first is None:
                    first = time.perf_counter() - start
                text.append(content)
            if event.get('done'):
                final = event
    if final is None:
        raise RuntimeError('Ollama cerró el stream sin evento final')
    elapsed = time.perf_counter() - start
    n = final.get('eval_count', 0)
    duration = final.get('eval_duration', 0)
    result = {'label':label, 'elapsed_seconds':round(elapsed,3),
              'first_content_seconds':None if first is None else round(first,3),
              'prompt_tokens':final.get('prompt_eval_count'), 'output_tokens':n,
              'tokens_per_second':None if not duration else round(n/(duration/1e9),3),
              'load_seconds':round(final.get('load_duration',0)/1e9,3),
              'prompt_eval_seconds':round(final.get('prompt_eval_duration',0)/1e9,3),
              'response': ''.join(text), 'done_reason':final.get('done_reason')}
    print(json.dumps({k:v for k,v in result.items() if k!='response'}, ensure_ascii=False), flush=True)
    return result

if __name__ == '__main__':
    report = {'real_model':True, 'replay':False, 'model_requested':MODEL,
              'backend':'Linux Docker CPU on Apple Silicon; no Metal passthrough',
              'threads_requested':THREADS, 'runs':[], 'ok':False}
    try:
        report['version'] = get_json('/api/version')
        show = get_json('/api/show', {'model':MODEL})
        report['details'] = show.get('details', {})
        report['capabilities'] = show.get('capabilities', [])
        report['renderer'] = show.get('renderer')
        report['parser'] = show.get('parser')
        if 'tools' not in report['capabilities']:
            raise RuntimeError('El modelo instalado no declara tools')
        for label, prompt in [
            ('cold', 'En tres frases explica qué prueba comparar una solicitud HTTP de control y una respuesta del receptor local en SSRF.'),
            ('warm', 'En tres frases explica por qué el XP debe calcularse por evidencia del servidor y no por una afirmación del agente.')]:
            report['runs'].append(trial(label, prompt))
        report['runtime_models'] = [{k:m.get(k) for k in ('name','model','digest','size','size_vram','context_length')} for m in get_json('/api/ps').get('models',[])]
        report['ok'] = True
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
