# Mercado Cordillera · VulnerableApp Academy

Laboratorio universitario, local y controlado para estudiar seguridad web con una tienda chilena ficticia. La aplicación conserva las rutas vulnerables de [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp), pero presenta los ejercicios dentro de **Mercado Cordillera** para resolverlos de tres formas:

1. desde la tienda simulada;
2. a mano, con `curl` y el cliente `lab` dentro de Kali;
3. con el harness docente y sus aprobaciones explícitas.

Todo el entorno se ejecuta en Docker Compose. No requiere una cuenta externa, una API key ni un Ollama instalado en el anfitrión.

## Qué contiene

El catálogo actual tiene **189 misiones en 20 familias**. Hay retos puntuables y prácticas guiadas/manuales. Cada ficha explica el objetivo, el control negativo, los pasos, las pistas, la mitigación y las limitaciones.

Las familias incluyen autenticación, inyección SQL/LDAP/comandos, SSRF, XXE, XSS, cargas de archivos, deserialización, IDOR, JWT, sesiones, OTP, recuperación de contraseña, path traversal, redirecciones, clickjacking, caché, criptografía y otras variantes del upstream fijado.

El laboratorio es deliberadamente vulnerable, pero las recetas docentes usan marcadores inocuos (`VA_LAB_OK`, `VA_LAB_RECEIVER`) y destinos internos del Compose. No se deben probar órdenes destructivas, secretos, reverse shells, destinos externos ni datos reales.

## Requisitos

- Docker Desktop o Docker Engine con Docker Compose v2.
- Navegador moderno.
- Conexión a Internet durante el primer build para descargar imágenes, dependencias y el modelo local.
- Aproximadamente 2,5 GB para los pesos de [Qwen3 4B en Ollama](https://ollama.com/library/qwen3:4b), además del espacio de las imágenes.

En Apple Silicon, Docker debe estar configurado para ejecutar imágenes Linux arm64/compatibles. El primer build puede tardar varios minutos; las ejecuciones posteriores usan la caché.

## Arranque rápido

Desde la carpeta del repositorio:

    git clone https://github.com/vtomasv/vulnerableapp-academy-public.git
    cd vulnerableapp-academy-public
    docker compose up -d --build --wait
    docker compose ps

Cuando los servicios aparezcan como `healthy`, abre:

**<http://localhost:8080>**

La portada es Mercado Cordillera. **Empezar primer reto** abre `commandInjection-02`, útil para comprobar rápidamente target, tienda, puntuación y sesión.

Si ya construiste las imágenes y solo quieres iniciar los contenedores:

    docker compose up -d --wait

Si usas otro nombre de proyecto, conserva ese nombre en todos los comandos para mantener los volúmenes separados:

    docker compose -p ethical-classroom up -d --build --wait

## Direcciones principales

| Desde | Servicio | Dirección |
|---|---|---|
| Anfitrión | Tienda y gateway | <http://localhost:8080/> |
| Anfitrión | Escritorio Kali/noVNC | enlace **Kali y harness**, o <http://localhost:8080/kali/vnc.html?autoconnect=1&resize=scale&path=websockify> |
| Anfitrión | Correo ficticio | <http://localhost:8080/mailpit/> |
| Kali | Target vulnerable | `http://target:9090/VulnerableApp/` |
| Kali | Tienda a través del gateway | `http://gateway:8080/` |
| Kali | Harness | `http://127.0.0.1:2323/` |
| Kali | Receptor local para SSRF/RFI | `http://receiver:8081/` |

El nombre `target` solo resuelve dentro de la red Docker. Desde el anfitrión no uses `http://target:9090`; entra por el gateway en `http://localhost:8080`.

## Recorrido recomendado

### 1. Resolver desde la tienda

1. Abre **Retos del taller** y elige una misión.
2. Lee el objetivo, el control negativo, la evidencia esperada y la mitigación.
3. Ejecuta primero **Cargar control** o el control indicado.
4. Marca la confirmación de revisión y pulsa **Enviar y verificar**.
5. Carga el ejemplo seguro, revisa método, ruta y parámetros, y envíalo.
6. Crea una cuenta ficticia en **Mi cuenta** cuando la tienda solicite guardar progreso.

El evaluador concede XP una sola vez por cuenta. Un HTTP 200 por sí solo no demuestra que un reto se haya resuelto: hay que comparar la respuesta con el criterio de la ficha.

### 2. Practicar a mano en Kali

Abre **Kali y harness** desde la tienda. En la terminal de Kali:

    lab login
    lab status

Usa la misma cuenta ficticia que registraste en la tienda. Para una solicitud exploratoria puedes usar `curl`; para registrar un intento puntuable usa `lab request`.

Ejemplo de inyección de comandos con un marcador benigno:

    curl -sS --get \
      --data-urlencode "ipaddress=127.0.0.1" \
      http://target:9090/VulnerableApp/CommandInjection/LEVEL_1

    curl -sS --get \
      --data-urlencode "ipaddress=127.0.0.1|printf VA_LAB_OK" \
      http://target:9090/VulnerableApp/CommandInjection/LEVEL_1

    lab request commandInjection-02 \
      --method GET \
      --param "ipaddress=127.0.0.1|printf VA_LAB_OK"

    lab status

La respuesta positiva esperada es:

    {"content":"VA_LAB_OK","isValid":true}

Para SQLi, codifica siempre los parámetros:

    curl -iG \
      http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_1 \
      --data-urlencode "username=admin_sqli" \
      --data-urlencode "password=' OR 1=1 --"

El uso de `--data-urlencode` evita perder espacios, comillas, pipes, `$` y otros caracteres especiales.

### 3. Practicar con el harness

1. Abre **Harness del taller** en el escritorio Kali.
2. Si solicita un directorio, elige `/home/kali`.
3. Pide primero `lab_missions` para consultar la misión exacta.
4. Pide `lab_http` para el control y luego para el payload.
5. Revisa método, ruta, parámetros y destino en el panel.
6. Pulsa **Allow once** solo si los argumentos coinciden con la ficha.
7. Pide `lab_submit` para registrar evidencia y después `lab_progress` para consultar XP.

El modelo no calcula ni modifica el puntaje: Academy verifica la evidencia real del servidor. No introduzcas contraseñas, cookies o tokens en el chat del harness.

## Error frecuente de curl

Este comando falla:

    curl -i "http://target:9090/VulnerableApp/AuthenticationVulnerability/LEVEL_1?username=admin_sqli&password=' OR 1=1 --"

El shell conserva la cadena completa, pero la URL todavía contiene espacios sin codificar. Curl responde `URL rejected: Malformed input to a URL function`.

Usa `--data-urlencode`, como en los ejemplos anteriores. Si ejecutas desde el anfitrión, cambia `target:9090` por el gateway:

    curl -iG \
      http://127.0.0.1:8080/VulnerableApp/AuthenticationVulnerability/LEVEL_1 \
      --data-urlencode "username=admin_sqli" \
      --data-urlencode "password=' OR 1=1 --"

## Puntuación y progreso

- La tienda muestra el progreso de la cuenta del taller.
- `lab request` y `lab_submit` registran evidencia en Academy.
- Repetir una misión ya completada puede devolver `0 XP` adicional: no es un fallo.
- Los retos guiados/manuales se evalúan con los pasos y la evidencia de la ficha; no todos tienen puntuación automática.
- Los niveles criptográficos aleatorios requieren razonamiento del alumno. `lab-crypto` ayuda con algunas semillas locales y solo registra puntos cuando se usa explícitamente `--submit`.

## Estado, logs y apagado

    docker compose ps
    docker compose logs --tail=80 model-init ollama gateway academy kali target
    docker compose stop

`stop` conserva contenedores y volúmenes. Para volver a arrancar:

    docker compose up -d --wait

Para borrar también cuentas, XP, correo, sesiones y pesos del modelo:

    docker compose down -v

Ese último comando es destructivo para los datos del laboratorio. En una clase, usa un proyecto Compose diferente por alumno:

    COMPOSE_PROJECT_NAME=va-alumno-01 LAB_PORT=8081 docker compose up -d --build --wait

## Configuración

Puedes copiar `.env.example` a `.env` y ajustar los valores antes de arrancar:

    COMPOSE_PROJECT_NAME=vulnerableapp-academy
    LAB_PORT=8080
    OLLAMA_MODEL=qwen3:4b
    OLLAMA_CPUS=4.0
    OLLAMA_MEMORY=6g
    OLLAMA_NUM_THREADS=4
    OLLAMA_CONTEXT_LENGTH=16384
    ACADEMY_CPUS=2.0
    ACADEMY_MEMORY=2g
    KALI_CPUS=2.0
    KALI_MEMORY=3g
    TARGET_CPUS=2.0
    TARGET_MEMORY=1g

Si `8080` está ocupado, cambia `LAB_PORT` y abre el nuevo puerto. Si el modelo tarda, revisa memoria/CPU de Docker y los logs de `ollama` y `model-init`.

## Diagnóstico rápido

    docker compose config --quiet
    docker compose ps -a
    docker compose logs --tail=120 target target-netlock gateway gateway-netlock academy kali

Problemas habituales:

- **Gateway no inicia:** espera a que `target-netlock`, `lab-netlock`, `academy` y `kali` estén `healthy`.
- **Kali/noVNC desconectado:** vuelve a abrir **Kali y harness** después de que `gateway` y `kali` estén saludables.
- **No se descarga el modelo:** revisa `model-init`; el primer arranque necesita Internet.
- **`target` no resuelve:** el comando se está ejecutando fuera de Kali; usa la URL del gateway o abre una terminal dentro del contenedor Kali.
- **`curl: (3) URL rejected`:** hay espacios o caracteres especiales sin codificar; usa `--data-urlencode`.
- **No se concede XP:** confirma que usaste `lab request`/`lab_submit`, una cuenta iniciada y el ID correcto; un `curl` directo solo es exploratorio.

## Verificaciones del repositorio

Las comprobaciones reproducibles se ejecutan dentro de Kali como el usuario no privilegiado `kali`:

    docker compose exec -T --user kali kali python3 \
      /opt/vulnerableapp-academy/tests/cordillera_ui_e2e.py

    docker compose exec -T --user kali kali python3 \
      /opt/vulnerableapp-academy/tests/harness_tools_e2e.py

La primera prueba cubre tienda, sesión, XP, repetición, práctica guiada, móvil y noVNC. La segunda cubre contrato del catálogo, descubrimiento acotado, solicitudes reales, marcador de command injection, límites del helper, sesiones, SSRF y puntuación repetida. La interacción con el modelo puede ser variable; el harness cerrado es la comprobación determinista.

Pruebas locales del backend:

    pytest -q tests/test_backend.py tests/test_harness_usability.py

## Documentación ampliada

- [Primer reto paso a paso](docs/COMENZAR.md)
- [Tutorial por familias y niveles](docs/TALLER.md)
- [Instalar y diagnosticar](docs/INICIO.md)
- [Guía completa del harness](docs/harness/GUIA.md)
- [Guía del instructor](docs/INSTRUCTOR.md)
- [Arquitectura](docs/ARQUITECTURA.md)
- [Seguridad y límites del laboratorio](docs/SEGURIDAD.md)
- [Atribuciones](docs/ATRIBUCION.md)

## Créditos

Adaptación docente independiente basada en [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp) y [S1N6H/pentest-harness](https://github.com/S1N6H/pentest-harness). El upstream Java se conserva en `vendor/` y la UI pública se limita a la tienda simulada y los retos del taller.
