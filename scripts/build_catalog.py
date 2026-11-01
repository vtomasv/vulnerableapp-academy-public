#!/usr/bin/env python3
"""Construye el catálogo local y su guía; no usa LLM ni servicios externos."""
import copy
import json
import re
import shlex
from pathlib import Path
from urllib.parse import urlsplit, quote

ROOT = Path(__file__).resolve().parents[1]
IDS = ['authentication', 'cachePoisoning', 'clickjacking', 'commandInjection',
       'cryptographicFailures', 'deserialization', 'fileupload', 'idor', 'jwt',
       'ldapInjection', 'openRedirect', 'otp', 'passwordReset', 'pathTraversal',
       'rfi', 'sessionManagement', 'sqlInjection', 'ssrf', 'xss', 'xxe']


def text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def route(value):
    if value.startswith('http://') or value.startswith('https://'):
        value = urlsplit(value).path
    return value.removeprefix('/VulnerableApp/').lstrip('/')


def command(m):
    args = ['lab', 'request', m['id'], '--method', m['method']]
    for k, v in (m.get('params') or {}).items():
        if isinstance(v, str) and '\x00' in v:
            args += ['--param-encoded', f'{k}={quote(v, safe="")}']
        else:
            args += ['--param', f'{k}={v}']
    for k, v in (m.get('headers') or {}).items():
        if k.lower() != 'content-type':
            args += ['--header', f'{k}={v}']
    if m.get('body') is not None:
        args += ['--body', str(m['body'])]
    if m.get('content_type'):
        args += ['--content-type', m['content_type']]
    return shlex.join(args)


def normalize_check(check):
    check = copy.deepcopy(check or {'kind': 'manual', 'value': 'Inspección guiada.'})
    if check.get('kind') == 'all':
        check['checks'] = [normalize_check(c) for c in check.get('checks', [])]
    if check.get('path'):
        check['path'] = check['path'].removeprefix('$.').lstrip('/').replace('/', '.')
    return check


def build():
    families, missions = [], []
    titles = {
        'authentication': 'Autenticación y almacenamiento de contraseñas',
        'cachePoisoning': 'Envenenamiento de caché compartida',
        'clickjacking': 'Secuestro de clics y protección de marcos',
        'commandInjection': 'Inyección de comandos con marcadores seguros',
        'cryptographicFailures': 'Fallos criptográficos y contraseñas',
        'deserialization': 'Deserialización insegura',
        'fileupload': 'Carga de archivos y validadores',
        'idor': 'Referencias directas y acceso indebido a objetos',
        'jwt': 'Tokens JWT y validación criptográfica',
        'ldapInjection': 'Inyección LDAP',
        'openRedirect': 'Redirecciones abiertas',
        'otp': 'Validación y reutilización de códigos OTP',
        'passwordReset': 'Recuperación de contraseñas',
        'pathTraversal': 'Recorrido de rutas y controles de archivos',
        'rfi': 'Inclusión remota y carga de clases',
        'sessionManagement': 'Gestión de sesiones',
        'sqlInjection': 'Inyección SQL y controles de consultas',
        'ssrf': 'Solicitudes realizadas por el servidor (SSRF)',
        'xss': 'Ejecución de scripts en el navegador (XSS)',
        'xxe': 'Entidades externas XML y expansión acotada',
    }
    for family_id in IDS:
        f = json.loads((ROOT / 'research' / f'{family_id}.json').read_text())
        f['id'] = family_id
        f['title'] = titles[family_id]
        f['concept'] = text(f.get('concept', ''))
        f['limitations'] = text(f.get('limitations', ''))
        for level in f.get('levels', []):
            level['notes'] = text(level.get('notes', ''))
            level['parameters'] = text(level.get('parameters', {}))
        families.append(f)
        exercises = f.get('exercises', [])
        for index, e in enumerate(exercises, 1):
            m = copy.deepcopy(e)
            m.update(id=f'{family_id}-{index:02d}', family=family_id,
                     route=route(e.get('route', '')), method=e.get('method', 'GET').upper())
            m['description'] = text(e.get('expected', e.get('explanation', '')))
            m['limitations'] = f['limitations']
            m['check'] = normalize_check(e.get('check'))
            m['params'] = e.get('params') or {}
            m['headers'] = e.get('headers') or {}
            m['body'] = e.get('body')
            m['content_type'] = e.get('content_type')
            if m['body'] and m['content_type'] == 'application/x-www-form-urlencoded':
                m['params'] = {}
            m['requirements'] = []
            m['tool'] = 'http_request'
            structured = (any(not isinstance(v, str) for v in m['params'].values())
                          or any(not isinstance(v, str) for v in m['headers'].values())
                          or isinstance(m['body'], (dict, list)))
            if family_id == 'xxe':
                m['params'] = {}
                structured = False
            if family_id == 'cryptographicFailures' and index <= 10:
                m['check'] = {'kind': 'json', 'path': 'isValid', 'value': True}
                m['description'] += '\nObjetivo puntuable: resolver el reto actual y enviar password correcta. Abrir el reto o enviar VA_LAB_WRONG no entrega puntos.'
            if family_id == 'cryptographicFailures' and index == 11:
                m['check'] = {'kind': 'manual', 'value': 'Analizar el control BCrypt seguro; leer el reto no es resolverlo.'}
            if family_id == 'jwt' and index in {3, 11}:
                m['check'] = {'kind': 'header_contains', 'header': 'Set-Cookie',
                              'value': 'httponly' if index == 3 else 'JWT='}
            if family_id == 'jwt' and index in {1, 9, 15, 16, 17}:
                m['check'] = {'kind': 'manual', 'value': 'Adquirir y validar el token de la misma instancia según los comandos; fetch por sí solo no acredita el objetivo.'}
            # Marker específico servido por receiver, nunca un booleano genérico.
            if family_id == 'ssrf' and m['check'].get('value') is True:
                m['check'] = {'kind': 'all', 'checks': [
                    {'kind': 'json', 'path': 'isValid', 'value': True},
                    {'kind': 'contains', 'path': 'content', 'value': 'VA_LAB_RECEIVER'}]}
                m['baseline'] = {'route': m['route'], 'method': 'GET',
                                 'params': {'fileurl': 'not-a-url'},
                                 'check': {'kind': 'json', 'path': 'isValid', 'value': False}}
            # XSS: el marcador DOM proviene de Chromium en el runner, no del cuerpo reflejado.
            if family_id == 'xss' and m['check']['kind'] == 'manual':
                raw = text(m['params']) + ' ' + text(m.get('body')) + ' ' + text(e.get('steps', []))
                marker = re.search(r'VA_XSS_[A-Z0-9_]+', raw)
                if marker and 'NEG' not in marker.group() and ('dataset.vaLab' in raw or 'dataset.vaLab' in text(m['check'])) and m['method'] == 'GET':
                    # Solo entradas explícitas, no instrucciones para múltiples peticiones.
                    if all(isinstance(v, str) for v in m['params'].values()) and m['params']:
                        m['tool'] = 'browser_probe'
                        m['check'] = {'kind': 'browser_dataset', 'path': 'vaLab', 'value': marker.group()}
                        m['description'] += '\nVerificación: Chromium dentro de Kali debe ejecutar el marcador DOM inocuo. La reflexión sola no otorga puntos.'
            # Una ausencia en el cuerpo no demuestra ausencia de una cabecera.
            if family_id == 'openRedirect' and m['check'].get('value') == 'Location:':
                m['check'] = {'kind': 'absent_header', 'header': 'Location', 'status': 200}
            if family_id == 'openRedirect' and m['check']['kind'] == 'header':
                m['check']['status'] = 302
            if family_id == 'openRedirect' and 'untrusted redirect target' in str(m['check'].get('value')):
                m['check']['status'] = 403
            if family_id == 'openRedirect' and 'unknown destination' in str(m['check'].get('value')):
                m['check']['status'] = 400
            # Controles negativos usan una respuesta específica + estado válido.
            if family_id == 'commandInjection':
                if m['check']['kind'] == 'contains':
                    previous = next((x for x in exercises if x.get('route') == e.get('route')
                                     and x.get('check', {}).get('kind') == 'not_contains'), None)
                    if previous:
                        m['baseline'] = {k: copy.deepcopy(previous.get(k)) for k in
                                         ['route', 'method', 'params', 'headers', 'body', 'content_type', 'check']}
                        m['baseline']['route'] = route(m['baseline']['route'])
                        m['baseline']['check'] = normalize_check(m['baseline']['check'])
            # Todo lo que aún requiere prueba manual queda identificado y sin puntos.
            manual = (m['check']['kind'] == 'manual' or not m['route'] or structured
                      or not re.fullmatch(r'[A-Za-z0-9_./-]+', m['route'])
                      or m['method'] not in {'GET', 'POST', 'PUT'})
            if manual:
                m['check'] = {'kind': 'manual', 'value': text(m['check'].get('value', 'Práctica guiada'))}
                m['points'] = 0
            else:
                m['points'] = 60 if m['check']['kind'] in {'not_contains', 'absent_header'} else 100
            m['verification'] = 'Práctica guiada sin puntaje automático' if manual else 'Evidencia observada por el runner de Kali'
            m['command'] = command(m)
            m['steps'] = [text(s) for s in e.get('steps', [])]
            if not manual:
                m['steps'] += ['Registrar la misma prueba con el cliente del laboratorio:\n' + m['command']]
            missions.append(m)
    catalog = {'version': 1, 'upstream_commit': (ROOT / 'vendor/UPSTREAM_COMMIT').read_text().strip(),
               'families': families, 'missions': missions}
    overrides = ROOT / 'academy/data/overrides.json'
    if overrides.exists():
        patches = json.loads(overrides.read_text())
        for m in missions:
            if m['id'] in patches:
                m.update(patches[m['id']])
                m['command'] = command(m)
                if m['points']:
                    m['verification'] = 'Evidencia observada por el runner de Kali'
                    m['steps'] = ['Lee el objetivo y contrasta la entrada con su mitigación. La siguiente receta usa la distribución y fixtures de este proyecto.',
                                  m['command'], 'Observa success, awarded y la evidencia devuelta; repetir una misión lograda no duplica sus puntos.']
                else:
                    m['verification'] = 'Práctica guiada sin puntaje automático'
            if m['tool'] == 'browser_probe':
                m['headers'] = {}
                m['content_type'] = None
                m['command'] = command(m)
    (ROOT / 'academy/data/catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Taller completo de VulnerableApp Academy', '',
             'El tutorial cubre las familias del repositorio Java fijado al commit indicado en `vendor/UPSTREAM_COMMIT`. '
             'No incluye por extensión aplicaciones de otros repositorios como VulnerableApp-JSP, VulnerableApp-PHP o LLMForge.', '',
             'Todos los comandos se ejecutan **dentro de Kali**, contra los nombres Docker del laboratorio. '
             'Los comandos `curl` directos son exploratorios; para puntaje usa `lab request`. '
             'Las prácticas marcadas como manuales no tienen verificador automático ni puntos. '
             'Los criterios prueban el hecho concreto indicado, no una certificación general de explotación o seguridad.', '',
             'Antes de avanzar, lee [Inicio](INICIO.md) y [Herramientas](HERRAMIENTAS.md). '
             'No saltes el control negativo: evita confundir una respuesta habitual con una vulnerabilidad.', '']
    for f in families:
        lines += [f"## {f['title']}", '', f['concept'], '', '### Todos los niveles originales', '']
        for l in f.get('levels', []):
            lines += [f"#### `{l.get('method','GET')} {l.get('route','')}`", '',
                      '**Entrada:** ' + text(l.get('parameters', '')), '',
                      text(l.get('behavior', '')), '', text(l.get('notes', '')), '']
        for m in [x for x in missions if x['family'] == f['id']]:
            lines += [f"### {m['id']} · {m['title']}", '', m['description'], '',
                      f"**Puntaje:** {m['points']} XP. {m['verification']}.", '',
                      text(m.get('explanation', '')), '']
            for step in m['steps']:
                step = step.replace('\x00', '%00')
                if step.startswith('curl ') or step.startswith('lab '):
                    lines += ['```bash', step, '```', '']
                else:
                    lines += [step, '']
            lines += ['**Criterio del verificador:**', '', '```json', text(m['check']), '```', '']
            if m.get('baseline'):
                lines += ['El verificador también ejecuta y contrasta este control definido por el servidor:', '',
                          '```json', text(m['baseline']), '```', '']
            lines += ['**Pistas:**', '', *[text(h) + '\n' for h in m.get('hints', [])],
                      '**Corrección recomendada:** ' + text(m.get('mitigation', '')), '']
        lines += ['### Límites de esta familia', '', f['limitations'], '']
    lines += ['## Procedencia y alcance', '',
              'La guía se deriva del código y pruebas del original; las expectativas estáticas no equivalen a una '
              'ejecución de todo el stack en cada sistema operativo. Consulta `docs/VALIDACION.md` para saber qué '
              'pruebas se realizaron y cuáles debes ejecutar en tu entorno.', '',
              'Fuentes: [repositorio original](https://github.com/SasanLabs/VulnerableApp), '
              '[documentación original](https://sasanlabs.github.io/VulnerableApp), '
              '[Qwen3](https://ollama.com/library/qwen3), '
              '[herramientas Ollama](https://docs.ollama.com/capabilities/tool-calling).', '']
    (ROOT / 'docs/TALLER.md').write_text('\n'.join(lines).rstrip() + '\n')
    print(f'{len(families)} familias; {sum(len(f.get("levels", [])) for f in families)} niveles; '
          f'{len(missions)} prácticas; {sum(m["points"] > 0 for m in missions)} misiones puntuables; '
          f'{sum(m["points"] for m in missions)} XP máximo')


if __name__ == '__main__':
    build()
