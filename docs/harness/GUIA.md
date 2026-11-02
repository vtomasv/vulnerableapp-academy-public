# Harness del taller: recorrido del alumno

Este laboratorio incluye el motor original **S1N6H/pentest-harness**, compilado y fijado al commit indicado en [FUENTES.md](FUENTES.md). Su preset predeterminado es **Taller VulnerableApp**. El harness usa Ollama local, tres skills docentes y herramientas acotadas de Kali; no es un shell libre controlado por el modelo.

## 1. Abrir el laboratorio

Desde la carpeta del repositorio en Windows, Linux o macOS, ejecutar:

```bash
docker compose up --build
```

La primera construcción necesita Internet para las imágenes, paquetes y pesos. Una vez preparado el volumen del modelo, las redes de ejecución son internas. Abrir el portal en `http://localhost:8080`, crear una cuenta propia y entrar en **Kali**. En el escritorio noVNC, abrir **Harness del taller** o ejecutar en una terminal de Kali:

```bash
firefox-esr http://127.0.0.1:2323
```

Elegir el preset **Taller VulnerableApp**, no el preset genérico de pentesting. Si la interfaz pide una carpeta de trabajo, usar `/home/kali`. El harness y el adaptador arrancan automáticamente: no es necesario ejecutar otra copia del servidor, instalar Node ni aportar una API key externa.

## 2. Vincular el progreso individual

En la terminal de Kali:

```bash
lab login
lab status
```

Usar la misma cuenta del portal. No escribir la contraseña ni el token en el chat del modelo. El progreso pertenece a esa cuenta; la API de Academy es quien valida el objetivo y concede XP. Para clases simultáneas, usar **una instancia Compose por alumno**. No compartir en paralelo una misma terminal o escritorio Kali: `lab login` es una sesión local por usuario Unix.

## 3. Reconocer las máquinas del Compose

Enviar al harness:

> Carga el skill vulnerableapp-scope. Después usa lab_discover con service all para reconocer las máquinas de este laboratorio. Explica IP, servicio, puerto y el comando Nmap real. No explotes nada todavía.

Cada llamada necesita una aprobación única en el panel del harness. Aprobar el skill no autoriza el siguiente escaneo. Los nombres permitidos son `target`, `receiver`, `mailpit`, `academy` y `ollama`. `all` significa esos cinco nombres, no una subred ni otros proyectos Docker. Sus puertos son 9090, 8081, 8025, 8000 y 11434 respectivamente; sus IP se asignan dinámicamente.

El comando real de una comprobación manual equivalente, dentro de Kali, es:

```bash
nmap -sT -n -Pn -sV --version-light -p 9090 target
```

La herramienta muestra el comando con la IP resuelta y sus límites de tiempo. Un timeout o un puerto no confirmado deben explicarse como tales, nunca transformarse en un descubrimiento inventado.

## 4. Comparar un control y un payload HTTP

Abrir en el portal la misión deseada y copiar su identificador, ruta y receta. El catálogo completo está también en `/opt/vulnerableapp-academy/docs/TALLER.md`.

Ejemplo de inyección SQL ciega, misión `sqlInjection-01`:

> Carga vulnerableapp-http. Usa lab_http para sqlInjection-01 con GET, params {"id":"999"}, headers {}, body null. Explica el control. Luego propón, sin ejecutar aún, el cambio a {"id":"100 OR 2=2"}.

Tras revisar el control, aprobar por separado el segundo intento. Los comandos manuales equivalentes son:

```bash
curl -sS --noproxy '*' --get --data-urlencode 'id=999' http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1
curl -sS --noproxy '*' --get --data-urlencode 'id=100 OR 2=2' http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1
```

Comparar los cuerpos JSON, no solo el estado `200`. Esta misión es una práctica manual de contraste y no concede XP automáticamente. El harness admite GET, POST y PUT según el catálogo, parámetros de texto, cabeceras válidas y cuerpo de hasta 16 KiB. No acepta un host o una ruta arbitrarios; la ruta procede del identificador de misión. No sigue redirects.

## 5. Registrar una misión con puntaje

Ejemplo local de SSRF, misión `ssrf-01`:

> Carga vulnerableapp-evidence. Para ssrf-01, prepara lab_submit con request GET, params {"fileurl":"http://receiver:8081/"}, headers {}, body null. Antes de ejecutarlo explica que el destino es el receptor inocuo del Compose y espera mi aprobación. Después informa solo el éxito y XP que devuelva Academy.

Una comprobación manual del mismo endpoint es:

```bash
curl -sS --noproxy '*' --get --data-urlencode 'fileurl=http://receiver:8081/' http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_1
lab request ssrf-01 --method GET --param 'fileurl=http://receiver:8081/'
lab status
```

`lab_http` muestra evidencia pero no concede puntos. `lab_submit` y `lab request` piden evaluación al servidor. Una misión lograda se puntúa una sola vez; repetirla no debe sumar XP nuevamente. Una práctica manual puede quedar sin puntaje aunque el alumno complete correctamente su razonamiento.

## 6. XSS, formularios y otras familias

Para XSS, leer la receta del nivel y usar su marcador inofensivo. Una cadena reflejada en HTML no prueba ejecución JavaScript: Academy usa el navegador de Kali para las misiones con criterio de navegador. Para formularios POST, usar el cuerpo y `content_type` del nivel sin duplicar los parámetros de query. Para XXE o SSRF, usar solo las fixtures y el receptor local de las recetas. No apuntar al anfitrión, Internet ni otras redes.

El catálogo incluye las veinte familias del original y conserva prácticas manuales cuando no existe un verificador suficiente. El harness ayuda a ejecutar y explicar solicitudes del catálogo, pero no convierte todas las prácticas manuales en pruebas automáticas ni reemplaza el análisis del alumno. Consultar [TALLER.md](../TALLER.md) y [HERRAMIENTAS.md](../HERRAMIENTAS.md) para los recorridos de cada familia y sus herramientas manuales de Kali.

## 7. Rechazar, detener y terminar

Rechazar una llamada en el panel debe impedir su ejecución. Una aprobación anterior no se reutiliza. Si una herramienta no pertenece a `lab_discover`, `lab_http`, `lab_submit` o `skill`, la guarda la bloquea aunque un prompt intente pedir bash, leer archivos, delegar o cambiar políticas.

Al terminar:

```bash
lab export
lab logout
```

Cerrar la sesión del portal si el equipo es compartido. Detener el taller desde la terminal del anfitrión con `Ctrl+C`, o con `docker compose stop`. No usar `docker compose down -v` salvo que se quiera borrar deliberadamente el progreso y los pesos locales.

## Interpretar fingerprint y consumo de CPU

El reconocimiento primero intenta la detección de versión con un límite corto. Si no obtiene una fila abierta, hace una segunda prueba Nmap TCP del **mismo IP y puerto**. Cuando esa confirmación es positiva pero el fingerprint no lo es, el resultado indica puerto abierto y versión no confirmada. No atribuir un producto por el nombre de puerto que Nmap usa como heurística.

Los modelos de CPU pueden tardar y deben probarse en el equipo del aula. El perfil usa una persona docente compacta, cuatro hilos y una generación predeterminada breve; las explicaciones extensas están en el tutorial estático. Las variantes más grandes pueden usarse como opción de instructor, pero una llamada nativa aislada exitosa no demuestra que el flujo completo con contexto y aprobación funcione bien en ese hardware.
