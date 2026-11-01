#!/usr/bin/env python3
"""Solución guiada de los retos 2–10. Solo target, sin listas externas ni envío automático."""
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
from urllib.request import build_opener, ProxyHandler

COMMON = ['riverside123!', 'coffeehouse27', 'blueberry2021', 'mountainview42',
          'summerbreeze24', 'sunflower2020', 'greenapple123', 'redrose12345',
          'chocolate2022', 'silverfox99']


def crypto_import():
    try:
        from Cryptodome.Hash import MD4
        from Cryptodome.Cipher import DES
    except ImportError:
        from Crypto.Hash import MD4
        from Crypto.Cipher import DES
    return MD4, DES


def lm_hash(password):
    _, DES = crypto_import()
    raw = password.upper().encode('ascii')[:14].ljust(14, b'\0')
    result = b''
    for offset in [0, 7]:
        k = raw[offset:offset+7]
        keys = [k[0] >> 1, ((k[0] & 1) << 6) | (k[1] >> 2),
                ((k[1] & 3) << 5) | (k[2] >> 3), ((k[2] & 7) << 4) | (k[3] >> 4),
                ((k[3] & 15) << 3) | (k[4] >> 5), ((k[4] & 31) << 2) | (k[5] >> 6),
                ((k[5] & 63) << 1) | (k[6] >> 7), k[6] & 127]
        key = bytes((v << 1) & 255 for v in keys)
        result += DES.new(key, DES.MODE_ECB).encrypt(b'KGS!@#$%')
    return result.hex()


def solution(level, content):
    value = re.search(r': ([A-Za-z0-9+/=]+) —', content)
    if level in {2, 3, 4}:
        if not value:
            raise ValueError('No se reconoció el formato del reto; consulta la guía y no inventes una respuesta.')
        cipher = value.group(1)
        if level == 2:
            return base64.b64decode(cipher, validate=True).decode(), 'Base64 es codificación reversible, no cifrado.'
        if level == 4:
            return base64.b64decode(cipher, validate=True).decode()[::-1], 'Decodificar Base64 y revertir la cadena reproduce el cifrado personalizado.'
        password = ''
        for ch in cipher:
            if 'a' <= ch <= 'z':
                password += chr((ord(ch)-ord('a')-3) % 26 + ord('a'))
            elif 'A' <= ch <= 'Z':
                password += chr((ord(ch)-ord('A')-3) % 26 + ord('A'))
            else:
                password += ch
        return password, 'César de desplazamiento 3: restar 3 a letras, conservar dígitos.'
    if level == 10:
        return 'aa123456', 'El seeder público fija la clave de este reto AES. Es una pista del laboratorio, no una técnica universal de descifrado.'
    digest = re.search(r'\b[0-9a-fA-F]{32,64}\b', content)
    if not digest:
        raise ValueError('La respuesta no contiene un hash reconocido.')
    expected = digest.group().lower()
    if level == 5:
        MD4, _ = crypto_import()
        fn = lambda p: MD4.new(p.encode()).hexdigest()
    elif level == 8:
        fn = lm_hash
    else:
        algorithm = {6: 'md5', 7: 'sha1', 9: 'sha256'}[level]
        fn = lambda p: hashlib.new(algorithm, p.encode()).hexdigest()
    for candidate in COMMON:
        if fn(candidate).lower() == expected:
            return candidate, 'Se compararon hashes LOCALMENTE sobre las 10 semillas públicas. No se hizo fuerza bruta en red ni se usó un servicio externo.'
    raise ValueError('No coincide con las 10 semillas de este commit. Detente y revisa el despliegue; no se amplía la búsqueda.')


def main():
    p = argparse.ArgumentParser(description='Ayuda opcional después de intentar resolver el reto; solo laboratorio local')
    p.add_argument('level', type=int, choices=range(2, 11))
    p.add_argument('--submit', action='store_true', help='Enviar el resultado con TU sesión lab; sin esta opción solo explica e imprime')
    args = p.parse_args()
    url = f'http://target:9090/VulnerableApp/CryptographicFailures/LEVEL_{args.level}'
    with build_opener(ProxyHandler({})).open(url, timeout=10) as r:
        content = json.loads(r.read(16384))['content']
    password, explanation = solution(args.level, content)
    print(content)
    print('\nExplicación:', explanation)
    command = ['lab', 'request', f'cryptographicFailures-{args.level:02d}', '--method', 'GET', '--param', 'password=' + password]
    print('\nPara registrar el objetivo con tu cuenta:\n' + shlex.join(command))
    if args.submit:
        return subprocess.run(command, shell=False, check=False).returncode
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, ImportError) as e:
        raise SystemExit('lab-crypto: ' + str(e))
