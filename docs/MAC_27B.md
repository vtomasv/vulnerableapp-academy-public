# Laboratorio real en Mac: Qwen 3.8 27B dentro de Docker

Esta guía describe la prueba local realizada en un **Apple M3 Max con 128 GB de RAM**, manteniendo target, Kali/noVNC, harness, Academy y Ollama dentro del Compose. No se instaló un Ollama nativo ni se usó un modelo remoto como sustituto. El modelo seleccionado es `huihui_ai/Qwen3.8-abliterated:27b`, con digest `bdc5e13cd1645bc409e95a7d9e864dc3ce3e5fe5beeb24a43c193e8041edd3e0`.

## Recursos y expectativas

Docker Desktop en este equipo ofrece una VM Linux ARM64 con 16 CPU y 64 GiB de memoria. No se cambiaron los recursos globales ni se detuvieron otros proyectos. El perfil permite al contenedor Ollama hasta 12 CPU y 48 GiB, con 12 hilos de inferencia y contexto de 16384 para el harness. Son límites, no reservas exclusivas: el escritorio y los otros servicios comparten la VM.

En el microbenchmark inicial, la API `/api/ps` reportó 18.214.478.149 bytes del modelo cargado, contexto 8192 y `size_vram=0`. El registro identificó 27,3B parámetros, GGUF Q4_K_M, renderer `qwen3.8`, parser `qwen3.5` y familia interna `qwen35`. Esta metainformación no es una sustitución por otro modelo: se obtuvo de la etiqueta y digest exigidos. La versión del runtime es **Ollama 0.40.13**.

**La prueba en Docker Mac es de CPU, no de Metal.** Los 128 GB físicos del Mac no se convierten automáticamente en memoria de la VM. Este perfil grande debe validarse en cada equipo del aula antes de entregar instrucciones a los alumnos. No se afirma compatibilidad de memoria ni igual rendimiento para laptops pequeñas o para Windows/Linux que todavía no han ejecutado esta versión.

## Arrancar sin instalar las herramientas en el Mac

Instalar Docker Desktop/Compose. Git es opcional: se puede descargar el ZIP del repositorio. Con Git:

```bash
git clone https://github.com/vtomasv/vulnerableapp-academy-public.git
cd vulnerableapp-academy-public
docker compose up --build -d
```

El arranque público usa el modelo 27B por defecto. No necesita crear `.env`; `.env.example` documenta opciones para el instructor. En la primera construcción hay descargas de imágenes, Kali, dependencias y pesos. Los pesos y el progreso se conservan en volúmenes. No ejecutar dos inicializadores del mismo volumen al mismo tiempo.

La copia de prueba utiliza un `.env` local ignorado por Git y un nombre de proyecto Docker separado para no colisionar con otros trabajos. Desde la carpeta en la que descargaste el repositorio, consulta el estado con `docker compose ps`.

El portal es `http://localhost:8080`. Registrar una cuenta propia y abrir Kali desde el portal. El harness del taller está en `http://127.0.0.1:2323` **dentro de Firefox en Kali**, no en un puerto público del Mac. Si solicita carpeta, usar `/home/kali`.

## Comprobar salud y aislamiento

```bash
docker compose ps
docker compose exec -T ollama ollama list
docker compose exec -T kali sh -c 'curl -fsS http://127.0.0.1:9001/health && curl -fsS http://127.0.0.1:11435/health'
docker compose exec -T --user kali kali lab doctor
```

Los servicios persistentes deben estar saludables. `init` y `model-init` terminan con código cero: no necesitan seguir ejecutándose. No hay montajes del socket Docker en Kali ni acceso del modelo al host. Los netlocks limitan salida a nombres y puertos del laboratorio; nunca ampliar su alcance a una subred de la casa, oficina o del aula.

## Primera práctica

Dentro de la terminal Kali:

```bash
lab login
lab missions
lab status
```

Usar una cuenta individual del portal. No mandar credenciales al chat. Seguir [la guía del harness](harness/GUIA.md): cargar un skill, leer `lab_missions`, comparar control y payload con `lab_http`, enviar `lab_submit` y confirmar `lab_progress`. Una aprobación no se reutiliza. Un `curl` directo no asigna XP; `lab request` y `lab_submit` piden evaluación a Academy.

## Rendimiento medido del 27B

Se usó streaming nativo de `/api/chat`, `think=false`, 12 hilos y contexto 8192. Se limitaron ambas respuestas a 96 tokens para medir el motor, no evaluar una resolución de vulnerabilidad.

| Consulta | Tiempo total | Primer contenido | Carga del modelo | Generación |
|---|---:|---:|---:|---:|
| Primera/cold | 42,692 s | 25,032 s | 22,698 s | 5,435 tokens/s |
| Segunda/warm | 17,423 s | 2,382 s | 0,001 s | 6,383 tokens/s |

Las consultas tenían 78 y 80 tokens de entrada respectivamente. Ambas finalizaron por el límite `length`. Son dos observaciones, no un benchmark estadístico, y un prompt de agente con herramientas y resultados puede ser mucho más largo. No usar esos números como tiempos de aprendizaje ni prometer que cada llamada del harness tardará 2,38 segundos.

La prueba es reproducible con:

```bash
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/benchmark_qwen.py
```

## Primer caso nativo ya verificado

Con el contexto 16K, el modelo real completó `commandInjection-02`: cargó el skill HTTP, consultó catálogo, comparó control y payload, envió el intento a Academy y leyó el progreso. El servidor devolvió `success=true`, `awarded=100`, `score=100` y la misión en `completed`. No fue una respuesta replay ni un script que simulase al motor.

La UI registró **7 min 41 s**, ocho pasos, aproximadamente 7 min 38 s de LLM y 3,9 s de llamadas de herramienta. Ese tiempo no es una prueba de rapidez frente al alumno: la QA automatiza botones de aprobación, mientras una persona necesita leer. El `ping` de control quedó bloqueado por los permisos de la imagen; el caso verifica exclusivamente que `VA_LAB_OK` aparece al encadenar `printf`, no que ping funcione ni que HTTP 200 sea un exploit. El agente interpretó correctamente esa diferencia.

## Comandos manuales frente a harness

La comparación usa los mismos tres objetivos: marcador RCE benigno, una fila SQL ficticia BMW y SSRF al receptor local. En manual se ejecutan control y payload con `curl`, y se pide evaluación con `lab request`. En harness se consultan los IDs exactos, se realizan llamadas nativas con aprobación y se pregunta a Academy por el resultado. El registro reproducible no da por conseguido un objetivo antes de verlo en `completed` y en sus eventos.

```bash
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/harness_tools_e2e.py
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/test_harness_usability.py
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/mac_comparison.py
```

Estas pruebas crean cuentas **ficticias** y pueden cambiar la sesión demo de `lab login`; no usan credenciales personales. El script de comparación aprueba solo los parámetros inocuos que declara y falla/rechaza otras propuestas. Los resultados auditados y capturas de esta ejecución están junto a la página del repositorio; no confundir pruebas de contratos con acciones reales del modelo.

## Contexto del agente: una consulta breve no es un ejercicio completo

El microbenchmark anterior se hizo con contexto 8K. La primera ronda larga no llegó a puntuar tras skill/catálogo/control; los logs mostraron presupuesto reducido hasta 206 tokens. No se atribuye toda parada del agente únicamente al presupuesto: también puede pedir revisión humana. El perfil se amplió a contexto 16K y capacidad de salida de 4096 en el proveedor; el adaptador mantiene cada generación acotada. No se cambiaron herramientas, guardas ni permisos. El log que decía `threads=4` era una etiqueta fija antigua: la variable y las opciones nativas ya indicaban 12. Ahora el log usa el valor efectivo. La prueba del ejercicio completo es la que determina la usabilidad, no el microbenchmark.

## Problemas encontrados y corregidos en esta prueba

La edición local en Mac produjo archivos con modo 0600. Docker COPY conservaba ese modo y el usuario sin privilegios de Kali no podía leer el adaptador. El Dockerfile ahora normaliza lectura solo del material público, sin ampliar permisos de claves o sesiones.

El noVNC instalado interpreta `path` respecto de `/kali/`: el enlace antiguo duplicaba el prefijo y pedía `/kali/kali/websockify`. Los enlaces usan `path=websockify` y se verificó la conexión efectiva del escritorio desde el navegador del Mac. También se corrigió el retorno de `lab_submit` que perdía la variable de misión después de que Academy ya había evaluado el intento. Después del arreglo, las **22 pruebas reales del helper pasaron**: descubrimiento fijo, solicitudes, bloqueos, primer premio, repetición sin XP e independencia de cuentas.

## Conservar, cerrar y volver a usar

```bash
# En Kali, terminar una sesión de alumno:
lab export
lab logout

# En el anfitrión, detener sin borrar progreso ni modelos:
docker compose stop

# Reanudar:
docker compose up -d
```

No usar `docker compose down -v` para una pausa: borraría los volúmenes del proyecto, incluido el modelo grande. La página GitHub Pages publica solo presentación, capturas y documentación; nunca ejecuta o expone el target vulnerable.

## Fuentes

- [Etiqueta exacta Ollama](https://ollama.com/huihui_ai/Qwen3.8-abliterated:27b).
- [Ficha del autor en Hugging Face](https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated).
- [Ollama en Docker](https://docs.ollama.com/docker).
- [Harness upstream fijado](https://github.com/S1N6H/pentest-harness/tree/4638f38082bdf37cea03ad151905c4bb8662f6e9).

## Correcciones observadas en la prueba de aula

- **Framebuffers negros:** noVNC podía indicar conectado aunque XFCE compuesto no mostraba las ventanas. Desactivar composición en la sesión DBus de Kali y usar `resize=scale` produjo la captura real con los tres comandos visibles. El arranque incorpora esa corrección; no se cambió el escritorio del Mac.
- **Campo opcional:** el catálogo devolvía `content_type:null`, que Python aceptaba como ausencia pero Javascript rechazaba. El validador y schema del plugin se alinearon; cualquier string sigue sujeto a tamaño y prohibición CR/LF/NUL.
- **GET de QA:** una resolución DNS temporal interrumpió el sondeo de `/api/me` durante SQL, sin perder el primer premio. El script reintenta solo consultas de lectura y reanuda únicamente su cuenta `demo_harness_*`, con decisiones nuevas para llamadas que nunca se habían aprobado. No repite mutaciones a ciegas ni reutiliza aprobaciones.
- **Selector de QA:** una aprobación pendiente reemplaza el composer; reanudar no debe esperar un textarea inexistente. Se corrigió el verificador, no la evidencia del objetivo.

Para comenzar como alumno nuevo, usa tu propia cuenta y una **New Session** del harness. No heredes el texto ni el login demo de la prueba. `lab logout` elimina solo la sesión CLI, no el progreso del servidor.

### Dos aprobaciones que no deben confundirse

En SSRF, el agente mostró el marcador correcto y preguntó en el chat si el alumno aprobaba enviar evidencia, pero todavía no había llamado `lab_submit`. Responder que ya revisaste la evidencia permite que **proponga** la llamada; después el panel **Allow once** autoriza su ejecución. La prueba registró ese checkpoint explícito antes de enviar la misma plantilla observada. No se concedieron puntos solo por la respuesta del modelo. Para clase, usar pasos cortos y revisar el control antes de avanzar.

## Resultado comparativo final y límite del observador

| Objetivo | Manual | Qwen 3.8 27B / harness | Evidencia |
|---|---:|---:|---|
| commandInjection-02 | 100 XP | 100 XP | VA_LAB_OK solo en el payload |
| sqlInjection-07 | 100 XP | 100 XP | Fila BMW al inyectar la condición OR |
| ssrf-01 | 100 XP | 100 XP | Respuesta VA_LAB_RECEIVER desde target |
| **Total de cada cuenta** | **300 XP** | **300 XP** | **Confirmado por /api/me de Academy** |

El agente llegó a lab_submit y lab_progress en SSRF después del checkpoint. La UI registró dos turnos, con 5 min 50 s y 6 min 25 s de ejecución; no son una medición total comparable con las recetas manuales y hubo espera/recuperación de QA. El observador terminó con `No hubo submit nativo aprobado` porque su registro no conservó las dos últimas decisiones, aunque la API y el transcript sí confirmaron la ejecución, el evento de 100 XP y los tres completados. Se conservaron **16 decisiones capturadas**, sin inventar los dos nonces faltantes. El JSON público indica `approval_capture_complete=false` y `reconciled_with_api=true`. **El objetivo se consiguió; la suite del observador no se declara completamente verde.**

Se añadió un lock de observador único para que una cancelación del CLI no permita iniciar otra prueba mientras el proceso anterior sigue dentro de Docker. La cancelación de `docker exec` no se debe asumir equivalente a terminar su proceso invitado. La inferencia 27B de CPU es didáctica y auditable, pero no necesariamente rápida ni autónoma: requiere revisar resultados y checkpoints.

### Refresco de firewall y salud después de recrear Kali

La verificación final detectó un netlock unhealthy: el antiguo refresco borraba el marcador y vaciaba OUTPUT cada diez segundos, coincidiendo con el sondeo de salud. Se sustituyó por generación de reglas con DNS mientras sigue activo el conjunto anterior y un `iptables-restore` atómico. Mantiene exactamente los cinco destinos/puertos, OUTPUT DROP y bloqueo IPv6; no cambia el firewall del Mac. El marcador se publica por rename y el healthcheck compara namespace y política DROP. No se interpreta `unhealthy` como permiso para abrir salida a Internet.
