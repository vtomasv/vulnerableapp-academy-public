# Arquitectura local

## Servicios del Compose

`gateway` es Nginx sin root, con un único puerto publicado en `127.0.0.1:8080`. Sirve el portal desde `academy` y el WebSocket de noVNC desde `kali`. No publica la API Ollama, el runner, SMTP, el receptor ni VNC nativo. `/VulnerableApp/` redirige al escritorio Kali: el target deliberadamente vulnerable no debe compartir el origen web del portal y sus sesiones.

`academy` es FastAPI con SQLite. Autentica cuentas locales, entrega el catálogo, recibe intentos y calcula puntos. No envía HTTP directamente al target para evaluar: usa el runner autenticado de Kali. Los tokens son aleatorios y se guardan como digest en SQLite; el cliente web usa sessionStorage y el CLI un archivo de sesión con permisos 0600. Las contraseñas se derivan mediante scrypt con fallback PBKDF2, no se almacenan en claro.

`target` compila el Java original desde el commit vendorizado. Arranca la distribución expandida del bootJar para que `getResourceAsStream` pueda resolver de forma reproducible la fixture `scripts/training/va-training.txt` dentro del classpath. También dispone de `/tmp/va-training.txt` para XXE. Ambos contienen el marcador inocuo `VA_LAB_FILE`; no se montan archivos del anfitrión. El código fuente original se conserva sin editar: la personalización ocurre en el empaquetado y en servicios adicionales.

`kali` contiene XFCE, Xvfb, x11vnc, noVNC, Firefox, Chromium y todas las herramientas de la guía. El escritorio pertenece a UID 1000; el runner, a UID 1001. Supervisord inicia los programas y baja la identidad de cada proceso. El usuario del escritorio no tiene sudo ni la clave del harness. VNC solo escucha en loopback interno.

`receiver` recibe y registra peticiones locales con un marcador conocido. Permite comprobar SSRF sin llamar a un tercero. `mailpit` recibe SMTP del target y permite revisar OTP y enlaces de recuperación en un buzón ficticio. Estos registros pueden contener tokens de entrenamiento; no introduzcas datos personales.

`ollama` sirve la inferencia en la red interna `control`. `model-init` es temporal: inicia su propio Ollama en loopback y descarga el modelo al volumen compartido solo si todavía no existe. Si el modelo ya está guardado, el reinicio no requiere un pull. Los pesos no se incluyen en el ZIP: se descargan en el primer arranque.

`init` crea una clave aleatoria para el runner y prepara permisos de volúmenes. La clave se monta de solo lectura en Academy y Kali y no se entrega al portal ni al escritorio. No se emplean claves predeterminadas compartidas entre instalaciones.

## Aislamiento de red

Las redes `lab`, `control` y `frontend` son internas. La red normal `model_bootstrap` la utiliza solo el inicializador temporal del modelo. No se monta Docker socket, home del host ni dispositivos, no se usa privileged ni network_mode host.

Dos sidecars, `target-netlock` y `lab-netlock`, comparten exclusivamente el namespace de red de target y Kali. Solo ellos reciben NET_ADMIN para aplicar OUTPUT DROP con loopback, conexiones establecidas, Docker DNS y destinos/puertos locales explícitos. Kali puede llamar a target:9090, receiver:8081, academy:8000, Mailpit:8025 y Ollama:11434; el target puede llamar solo al receptor y a SMTP, además de loopback. IPv6 de salida queda restringido. Una marca con el identificador del namespace evita iniciar servicios con una marca persistida de una generación anterior.

Al actualizar reglas, la política sigue en DROP: no hay una ventana de OUTPUT ACCEPT. La defensa no equivale a una VM de seguridad perfecta; hay dependencias del motor y kernel. El tráfico DNS a través del resolver de Docker merece revisión si el aula necesita protección fuerte contra canales de exfiltración. Para ese caso utiliza una VM desechable y DNS/firewall del anfitrión dedicado al laboratorio.

## Intentos y puntuación

El alumno elige un identificador de misión y aporta parámetros, headers y cuerpo. Academy fija ruta, método permitido, criterio y recompensa desde el catálogo del servidor. Kali construye argumentos de curl sin shell y sin seguir redirecciones. La evaluación usa status, headers, body, exit_code y, en XSS, un dataset DOM fijo; nunca busca una cadena en el comando enviado como sustituto del resultado.

Las misiones de caché ejecutan limpieza local definida por servidor, el intento del alumno y una solicitud de visitante independiente. Stored XSS dispone de una segunda navegación sin el parámetro del atacante. Los casos que requieren pasos no correlacionados conservan su guía pero no se puntúan automáticamente.

La recompensa se concede en una transacción con clave única de usuario y misión. Repetir o enviar dos intentos concurrentes no duplica el premio. Las cuentas conservan progreso individual, pero el target y el escritorio son compartidos dentro de una instancia. No es un sistema anti-trampas ni una plataforma de examen supervisado.

## Tutor y herramientas

Qwen recibe un contexto acotado de la misión y la pregunta. El API local usa `/api/chat`, `stream: false`, `think: false`, contexto de 4096 tokens, generación acotada y hasta 180 segundos para CPU. Se declaran herramientas nativas `inspect_headers` y `lab_request`. También se reconocen propuestas JSON compatibles. Cualquier otro nombre se rechaza.

La propuesta queda pendiente por cinco minutos y ligada al alumno y la misión. La aprobación autenticada es explícita, de un solo uso y vuelve a comprobar tipos, cantidad de campos, tamaño, ruta y método. La herramienta no da puntos ni permite ejecutar shell, una URL arbitraria, JavaScript libre, escáneres libres o acceso a secretos. Para sumar puntos el alumno registra su propio intento.

La variante predeterminada Qwen3 ablacionada está publicada por huihui.ai y reduce el filtrado del modelo. No se promete ausencia total de rechazos, seguridad ni exactitud. El harness impone las restricciones externas incluso si el modelo produce instrucciones indebidas. La inferencia y los mensajes permanecen locales; no hay fallback a un proveedor de IA externo.
