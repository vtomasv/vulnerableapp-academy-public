# Validación y límites de prueba

La revisión posterior de inicio guiado, tienda chilena y navegador del Mac está en [Validación de Mercado Cordillera](VALIDACION_CORDILLERA.md). Las secciones históricas siguientes conservan su alcance original.

## Pruebas Docker reales de esta ampliación

El laboratorio se construyó y arrancó con Docker/Compose real en Linux ARM64. Se compilaron el Java original y el motor `S1N6H/pentest-harness` del commit fijado; se instalaron las herramientas, XFCE, VNC/noVNC, Node y el runtime del harness en Kali. Los inicializadores de secretos y pesos terminaron con código 0 y los servicios residentes quedaron saludables, incluidos los tres bloqueos de salida de target, Kali y gateway.

Se verificaron HTTP 200 del portal en `127.0.0.1:8080` y de noVNC en `/kali/vnc.html`, procesos vivos de XFCE, VNC, websockify, runner, adaptador y harness. Solo el gateway publica un puerto de localhost. La clave del runner es inaccesible al alumno, y el proceso `kali` UID 1000 tiene cero capabilities efectivas.

`tests/harness_tools_e2e.py` se ejecutó dentro de Kali como UID 1000: **22 PASS, 0 FAIL, 0 SKIP**. Usa el helper real, Nmap y curl auténticos y el evaluador de Academy; no reemplaza los cuerpos de los ejercicios por mocks. Comprueba:

- Resolución y puertos TCP abiertos de `target:9090`, `receiver:8081`, `mailpit:8025`, `academy:8000` y `ollama:11434` mediante Nmap. Si el fingerprint no termina, un segundo Nmap acotado confirma el puerto; no se inventa versión.
- SQL ciega `sqlInjection-01`: `id=999` devuelve `isCarPresent=false` y `id=100 OR 2=2` devuelve `true`.
- Inyección de comandos `commandInjection-02`: el proceso del target produce el marcador `VA_LAB_OK`.
- SSRF `ssrf-01`: petición al receptor local, éxito del criterio y 100 XP; repetir entrega 0 XP adicionales. Otra cuenta comienza con 0 XP.
- Rechazo de servicios/IP externos, misión desconocida, ruta/cabeceras de enrutamiento no permitidas, CRLF y cuerpo excesivo.
- Sesión privada del CLI, clave inaccesible, capabilities cero y salida externa bloqueada.

Los pesos Qwen comunitarios se descargaron realmente dentro de `model-init`. Su API nativa de Ollama produjo una llamada real `lab_discover` con `service=all`; no se usó replay. El recorrido completo de modelo → aprobación del harness → herramienta tiene un test separado, `tests/harness_ui_e2e.py`: su estado y las capturas se documentan en [Validación del harness](harness/VALIDACION.md). Un test unitario o una llamada nativa al modelo no equivalen a ese recorrido integrado.

También pasó `tests/harness_score_e2e.py`: Qwen 1,7B cargó `vulnerableapp-evidence`, pidió una segunda aprobación para `lab_submit` y el evaluador confirmó `ssrf-01` con 100 XP en una cuenta nueva. El resultado se leyó del API autenticado de Academy; no se tomó como prueba el puntaje escrito por el modelo. La aprobación del skill y la del intento tenían IDs distintos.

## Correcciones detectadas al probar Docker

Se eliminaron file capabilities del binario Nmap durante el build: Kali rolling las instala, pero son incompatibles con el runtime `cap_drop: ALL` y `no-new-privileges`. Se conserva Nmap TCP `-sT`, sin conceder NET_RAW ni NET_ADMIN al alumno.

Se retiró `curl --proto-redir =none`, rechazado por curl de Kali. El runner no usa `-L` y no sigue redirects. Se corrigió la importación del cliente `lab` sin extensión. El launcher fuerza su propia raíz de presets; por eso el preset docente se copia también a esa raíz oficial, sin modificar el código del motor.

Docker no materializó el puerto de un gateway conectado solo a redes internas. Se añadió una red de entrada exclusiva de gateway y su namespace conserva OUTPUT DROP con destinos fijos, IPv6 deshabilitado y DNS externo desviado. No se solucionó debilitando la red de Kali ni publicando el target.

## Validación de componentes anterior

El Java original se compiló con Java 17 y `./gradlew bootJar -x test` a partir de `4df80bbcd42682ecf26334f12c568e0f4a326c1a`. Antes de disponer del daemon se probaron 95 objetivos mediante API Academy → runner → curl/Chromium → target expandido, y otros 8 retos criptográficos de niveles 2–9: 103 objetivos puntuables distintos. El criptográfico nivel 1 no se resolvió en aquella validación.

El catálogo conserva **104 prácticas puntuables y 85 guiadas/manuales**. No se afirma que 189 prácticas sean exploits automáticamente verificados. Las recetas que no demostraron su hecho preciso se mantuvieron manuales y con 0 XP. Tampoco se ejecutó la suite completa del proyecto Java upstream.

Las diez pruebas unitarias `tests/test_backend.py` cubren autenticación, progreso, idempotencia, controles, caché, navegador, exportación y aprobación. Usan mocks de modelo/runner donde corresponde. La prueba anterior del portal registra un alumno, envía un intento y observa 100 XP, sin errores JS ni overflow a 390 px; no se confunde con el nuevo harness web.

## Repetición sin instalar Python en el anfitrión

```console
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose exec --user kali kali lab doctor
docker compose exec lab-netlock iptables -S OUTPUT
docker compose exec target-netlock iptables -S OUTPUT
docker compose exec gateway-netlock iptables -S OUTPUT
docker compose cp tests/harness_tools_e2e.py kali:/tmp/harness_tools_e2e.py
docker compose exec --user kali kali python3 /tmp/harness_tools_e2e.py
docker compose cp tests/harness_ui_e2e.py kali:/tmp/harness_ui_e2e.py
docker compose exec --user kali kali python3 /tmp/harness_ui_e2e.py
docker compose cp tests/harness_score_e2e.py kali:/tmp/harness_score_e2e.py
docker compose exec --user kali kali python3 /tmp/harness_score_e2e.py
```

La suite crea cuentas ficticias y deja una sesión de prueba del CLI. Para iniciar después el curso, usar `lab logout` y entrar con la cuenta del alumno. No requiere ese test para arrancar.

El smoke test adicional `scripts/smoke.sh` puede ejecutarse en Linux/macOS o WSL. Registra dos alumnos, repite una misión, exporta su JSON y reinicia Academy para comprobar persistencia en el equipo del aula. Para recrear target o Kali, recrea también su netlock; para gateway, incluye `gateway-netlock`.

## No probado y límites

No se validó Docker Desktop en Windows/macOS ni x86_64. Se diseñó sin emulación forzada, pero Kali rolling y las imágenes externas pueden cambiar. Antes de clase hay que probar un equipo de cada tipo que se utilizará.

No se ofrece garantía absoluta contra escapes del kernel, Docker, navegador, canales DNS o modificación por el dueño del anfitrión. Los datos deben ser ficticios. Una cuenta separa progreso, no el escritorio ni el target compartido: para simultaneidad, una instancia Compose por alumno.

## Prueba actual Mac / Qwen 3.8 27B

Docker Desktop Linux ARM64, M3 Max/128 GB, VM 16 CPU/64 GiB y Ollama 0.40.13. Se levantaron todos los servicios. 22 controles reales del helper y 8 contratos pasaron; el validador JS acepta content_type null sin relajar CRLF/Host. El modelo real consiguió RCE, SQL y SSRF, 300 XP en una cuenta distinta de la manual (también 300). El observador final perdió dos decisiones SSRF y terminó con error; el resultado de la misión se reconcilió contra API y transcript, no contra un supuesto éxito del test. Ver [MAC_27B](MAC_27B.md) y [datos públicos](../site/resultados.json). No se afirma haber probado los 189 ejercicios con el modelo ni esta versión en Windows/Linux x86_64.
