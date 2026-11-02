# VulnerableApp Academy — taller local en español

Laboratorio didáctico basado en [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp), con el código Java original fijado en `vendor/UPSTREAM_COMMIT`. Añade un portal con estética de videojuego, misiones, explicaciones y comandos reales; escritorio Kali XFCE por noVNC; tutor Ollama local; verificación de evidencia y progreso individual persistente.

## Arrancar

Descarga o clona **este repositorio completo**, abre una terminal en la carpeta y ejecuta:

```console
docker compose up --build -d
```

Abre **http://localhost:8080**, registra una cuenta y pulsa «Abrir Kali». En el escritorio, el acceso **Harness del taller** abre el agente de pentesting local. Solo necesitas Docker con Compose v2 y un navegador en Windows, Linux o macOS. No necesitas instalar Kali, Java, Python, Ollama, Git, Node, pnpm ni VNC en el anfitrión si descargaste el ZIP.

El primer arranque requiere Internet para descargar imágenes, paquetes y el modelo. Después los servicios de entrenamiento y la inferencia usan redes Docker internas. Solo el gateway tiene una red de entrada para publicar localhost, con su propio bloqueo de salida; la descarga del modelo es un servicio temporal independiente. Reserva aproximadamente 16 GB de RAM para Docker y **40 GB de disco libre** como orientación para imágenes y cachés de construcción, no como mínimo universal. El modelo predeterminado ocupa aproximadamente 1,1 GB de descarga; su uso de RAM es mayor.

El Compose está diseñado para Linux containers x86_64 y ARM64 sin forzar emulación. Se construyó y arrancó realmente en Linux ARM64; **no se ha validado Docker Desktop en Windows/macOS ni x86_64:** consulta [Validación](docs/VALIDACION.md). La versión de Kali rolling y las imágenes base son dependencias externas que pueden cambiar.

## Qué incluye

El catálogo cubre **20 familias**, con **187 entradas de nivel** del Java original y **189 prácticas**. Hay **104 prácticas puntuables** y **85 prácticas guiadas/manuales**, con un máximo de **9800 XP**. Una entrada de nivel no siempre equivale a una misión: algunas prácticas comparan dos niveles o varios estados.

Cada misión explica la entrada, la expectativa, los pasos, las pistas, la mitigación y el criterio observado. No afirma una vulnerabilidad solo porque hubo HTTP 200. XSS puntuable comprueba un marcador DOM benigno en Chromium de Kali; las misiones de caché verifican una segunda solicitud de visitante. Los casos sin correlación automática suficiente conservan su guía y no otorgan puntos.

Kali incluye Firefox, Chromium, curl, jq, Python, Java JDK, OpenSSL, nmap, sqlmap, ldapsearch, netcat, ZAP y herramientas de escritorio. Todas las herramientas que utiliza la guía están dentro de la imagen. Los accesos de escritorio abren VulnerableApp y Mailpit desde Kali. La aplicación deliberadamente vulnerable **no comparte origen web con el portal autenticado del anfitrión**.

El modelo predeterminado es `huihui_ai/qwen3-abliterated:1.7b-v2-q4_K_M`, una variante Qwen3 con filtrado reducido publicada por su autor. No se garantiza que nunca rechace una solicitud ni que sus respuestas sean correctas. El harness no depende de su moderación: permite solo operaciones definidas, exige aprobación del alumno y no le da una shell libre ni permisos de puntuación. Puedes elegir Qwen oficial con `OLLAMA_MODEL=qwen3:1.7b` en `.env`, o la variante comunitaria 4B como opción de instructor. La opción 4B no completó el flujo con contexto completo en la CPU de esta prueba.

## Harness de pentesting incluido

Kali integra **[S1N6H/pentest-harness](https://github.com/S1N6H/pentest-harness)**, compilado desde el commit `4638f38082bdf37cea03ad151905c4bb8662f6e9`. No se reemplaza por un script que imite al motor. Su perfil **Taller VulnerableApp** limita el modelo a `lab_discover`, `lab_http`, `lab_submit` y `skill`; cada llamada pide una aprobación nueva y una guarda adicional bloquea herramientas o argumentos fuera del alcance.

Se instalan los skills **vulnerableapp-scope**, **vulnerableapp-http** y **vulnerableapp-evidence**. El agente usa el Qwen local por un adaptador de protocolo en loopback, sin proveedores externos ni telemetría. `lab_submit` registra evidencia con la sesión de `lab login` y recibe el XP de Academy, no del modelo. Consulta la [guía del harness](docs/harness/GUIA.md) y su [arquitectura](docs/harness/ARQUITECTURA.md).

## Primer intento con puntaje

En la terminal del escritorio Kali:

```bash
lab login
lab missions
lab request commandInjection-02 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'
lab status
```

Introduce la misma cuenta del portal. La evidencia la produce el runner de Kali; el servidor calcula el puntaje y evita recompensas duplicadas. `curl` directo sirve para aprender, pero no entrega puntos porque no identifica al alumno. Las herramientas aprobadas al tutor tampoco suman puntos: usa tu intento de misión.

El progreso se guarda en SQLite en un volumen Docker. Sobrevive a reinicios y a `docker compose down` **sin** `-v`. El escritorio y las semillas del target son compartidos por las cuentas del mismo Compose; para clases simultáneas, cada alumno debe iniciar su Compose en su propio equipo. Cierra sesión tanto en el portal como con `lab logout` al compartir máquina.

## Guías y pruebas

Empieza por [Inicio paso a paso](docs/INICIO.md), sigue [Herramientas de Kali](docs/HERRAMIENTAS.md) y utiliza el [Tutorial completo](docs/TALLER.md). El instructor dispone de [Guía de facilitación](docs/INSTRUCTOR.md). Consulta [Seguridad y harness](docs/SEGURIDAD.md), [Modelo y arquitectura](docs/ARQUITECTURA.md), [Validación y pruebas pendientes](docs/VALIDACION.md) y [Fuentes](docs/FUENTES.md).

Las guías también están dentro de Kali en `/opt/vulnerableapp-academy/docs/`. El portal funciona sin fuentes, CDNs ni scripts externos.

En el anfitrión, `docker compose config --quiet` valida la configuración. Después del primer arranque, `scripts/smoke.sh` ejecuta las comprobaciones de runtime en Linux/macOS; en Windows puedes ejecutar el script desde WSL o seguir los comandos de [Validación](docs/VALIDACION.md). No se necesita ese script para iniciar el laboratorio.

## Alcance y licencia

Solo para entornos de práctica autorizados, aislados y con datos ficticios. No publiques los puertos, no montes el socket Docker ni carpetas sensibles del host, y no agregues destinos externos al harness. Docker no es una VM de seguridad absoluta; para cursos de alto riesgo usa una VM desechable adicional.

No se amplía el alcance automáticamente a VulnerableApp-JSP, VulnerableApp-PHP, LLMForge ni otros proyectos de SasanLabs. La aplicación original y esta distribución se entregan bajo Apache-2.0; se conserva la licencia y la procedencia del código original.

El motor pentest-harness conserva su licencia MIT en `/opt/pentest-harness/LICENSE`. Sus dependencias y los pesos del modelo conservan sus respectivas licencias. El repositorio no distribuye los pesos ni credenciales: se descargan y generan localmente mediante Compose.
