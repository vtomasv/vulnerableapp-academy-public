# Arquitectura del harness

## Motor original y perfil docente

Kali compila `S1N6H/pentest-harness` desde el commit `4638f38082bdf37cea03ad151905c4bb8662f6e9`, con Node 24 y pnpm 11.7 y su lockfile. El runtime original está en `/opt/pentest-harness/apps/cli/lib/bin.js`; su licencia MIT se conserva en `/opt/pentest-harness/LICENSE`.

El código del motor no se sustituye por una imitación. El laboratorio añade el plugin, preset, adaptador y tres skills en `/opt/academy-harness`. Estos archivos adicionales pertenecen a la distribución Apache-2.0. La raíz oficial de presets contiene también **Taller VulnerableApp**, porque el launcher original fuerza esa raíz al iniciar la UI.

## Alumno, runner y puntaje

El escritorio y el harness usan `kali`, UID 1000, sin sudo y con capabilities efectivas cero. Nmap usa TCP connect y no necesita NET_RAW. El runner del evaluador usa UID 1001 y una clave generada en un volumen protegido que UID 1000 no puede leer. El dueño de Docker sí controla la máquina: no se ofrece anti-cheat contra el administrador del anfitrión.

`lab login` guarda la sesión de la cuenta pedagógica en `/home/kali/.config/va-lab/session.json`, modo 600. No se pasa al prompt del modelo. `lab_submit` usa esa sesión mediante el cliente instalado y solicita evaluación a Academy. La cuenta pedagógica y su puntaje SQLite no son las cuentas vulnerables ni las semillas de H2 del target.

Solo Academy decide éxito y XP a partir del resultado del runner. El modelo no tiene una herramienta para escribir puntos. Las cuentas separan progreso, pero comparten escritorio y estado del target dentro de una instancia: para simultaneidad, una instancia Compose por alumno.

## Autorización por llamada

Las herramientas visibles son `lab_discover`, `lab_missions`, `lab_progress`, `lab_http`, `lab_submit` y `skill`. La guarda monotónica rechaza nombres y argumentos fuera del alcance aunque otro plugin devuelva permiso. El consumidor de aprobación pide una decisión nueva por llamada; `allowed-once`, `rejected`, `cancelled` y `unavailable` son los estados originales. Sin agente, canal o respuesta disponible, la operación falla cerrada.

El preset no instala herramientas genéricas de shell, filesystem, búsqueda externa, workflows o delegación. Los registries que la UI necesita no equivalen a herramientas autorizadas. Cargar un skill no aprueba un escaneo ni un intento posterior.

## Modelo local y protocolo

El predeterminado actual es `huihui_ai/Qwen3.8-abliterated:27b`, descargado en el volumen de Ollama 0.40.13. El perfil nativo usa contexto 16K, 12 hilos y capacidad de salida 4096 en el proveedor; la generación por solicitud sigue acotada por el adaptador. La variante comunitaria reduce filtrado, sin garantizar precisión ni ausencia de rechazos. Las pruebas anteriores con 1,7B se conservan como historial, no como perfil actual. Ver [prueba Mac/27B](../MAC_27B.md).

El adaptador escucha únicamente en `127.0.0.1:11435` de Kali. Acepta un solo modelo configurado, `/health`, `/v1/models` y `/v1/chat/completions`; convierte el protocolo OpenAI del cliente original al `/api/chat` nativo de `http://ollama:11434`. No sigue URLs del usuario, ignora proxies del entorno y no usa proveedores externos.

La solicitud nativa fija `think:false`, contexto 16384 y 12 hilos por defecto, parametrizados por Compose. La generación predeterminada del adaptador es 256 y su límite por solicitud es 1024; el proveedor dispone de presupuesto 4096 para no agotar la secuencia de pasos. La persona docente es un prompt completo para evitar instrucciones genéricas innecesarias; esto no desactiva los contextos de skills ni las guardas de ejecución. El adaptador registra solo conteos y tamaños, no los prompts ni credenciales.

## Interfaz y redes

El harness original escucha en 2323 dentro de Kali y se abre desde Firefox en el escritorio noVNC. VNC nativo permanece local; noVNC escucha en 6080 y se accede por el gateway `127.0.0.1:8080/kali/`. Solo ese gateway publica un puerto al anfitrión. El target no comparte origen web con la sesión del portal.

`lab`, `control` y `frontend` son redes internas. La red `ingress`, no interna, pertenece solo al gateway y existe para materializar la publicación de localhost. `gateway-netlock` comparte exclusivamente su namespace de red y aplica OUTPUT DROP: permite loopback, respuestas establecidas y Academy:8000, Kali:6080 y Mailpit:8025. IPv6 está deshabilitado y su DNS externo apunta a una dirección de documentación.

Target y Kali tienen sus propios bloqueos de salida mediante sidecars NET_ADMIN. Ese permiso no se concede a Java, al estudiante ni al modelo. Los servicios de bootstrap y build requieren Internet; el descargador de pesos termina después de preparar el volumen. No se monta el socket Docker ni directorios personales del anfitrión.

## Procesos de herramientas

`lab_discover` resuelve exclusivamente cinco nombres y pasa a Nmap un IP privado validado y un puerto fijo. Usa `-sT -n -Pn -sV --version-light` con límite de 15 segundos. Si no confirma apertura, una segunda prueba TCP del mismo IP y puerto tiene límite de 5 segundos de Nmap y 8 segundos de proceso. Apertura confirmada no significa versión confirmada.

Los procesos del helper se crean con argv y stdin JSON, no con una shell que interprete texto del modelo. `lab_http` toma su ruta del catálogo; valida método, parámetros, cabeceras y cuerpo. Conserva las restricciones de protocolo y tiempo de curl, no usa `-L` y rechaza cabeceras de enrutamiento reservadas. `lab_submit` envía esos mismos datos al evaluador autenticado.

Las herramientas normales de Kali siguen disponibles para el alumno en terminal. El harness no automatiza todos los pasos manuales de las veinte familias. Docker comparte kernel, las respuestas son no confiables y el aislamiento no es absoluto; se usan exclusivamente datos ficticios y fixtures locales.

Consultar [GUIA.md](GUIA.md), [VALIDACION.md](VALIDACION.md) y [FUENTES.md](FUENTES.md).
