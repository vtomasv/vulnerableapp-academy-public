# Iniciar el taller

Este laboratorio contiene una aplicación deliberadamente vulnerable. Úsalo únicamente en un equipo de prácticas, con datos ficticios. No cambies la publicación de `127.0.0.1` a `0.0.0.0`, no lo abras mediante túneles ni lo publiques en Internet. Docker comparte kernel con el anfitrión: para cursos de alto riesgo, ejecuta Docker dentro de una VM desechable.

## Preparación en Windows, Linux y macOS

Instala Docker con Compose v2. En Windows usa Docker Desktop con backend WSL2 y contenedores Linux; en macOS, Docker Desktop con contenedores Linux; en Linux, Docker Engine y el plugin Compose. No se necesitan Kali, Java, Python, Ollama ni un cliente VNC en el anfitrión. El navegador del anfitrión es suficiente para acceder al portal y al escritorio.

Descarga el repositorio como ZIP o clónalo si ya usas Git. Extrae la carpeta completa y abre una terminal en ella. El primer arranque necesita Internet para construir las imágenes y descargar Qwen. Después, los ejercicios y la inferencia se ejecutan localmente; no se envían conversaciones a un proveedor de IA.

```console
docker compose up --build -d
```

No copies `.env.example` si quieres usar los valores predeterminados: Compose ya tiene valores de respaldo. Si necesitas cambiar el puerto, el modelo o los recursos, crea `.env` desde el ejemplo **antes** del arranque. Las imágenes y el modelo requieren varios GB; como orientación de dimensionamiento, reserva 16 GB de RAM total para Docker y espacio libre holgado, preferentemente 25–35 GB. Son recomendaciones, no mínimos medidos ni garantías: la memoria de Chromium, Java y Qwen depende de la carga. Con poca RAM puedes seleccionar `huihui_ai/qwen3-abliterated:1.7b` en OLLAMA_MODEL; prueba su latencia y calidad antes del aula.

Abre `http://localhost:8080`. Si cambiaste `LAB_PORT`, utiliza ese puerto. La primera carga del modelo puede ser lenta en CPU; consulta el estado sin repetir la descarga:

```console
docker compose ps
docker compose logs --tail=80 model-init ollama academy kali target
```

## Tu identidad y tu progreso

Registra un nombre de alumno y una contraseña exclusiva para el laboratorio. Estas cuentas pertenecen al portal pedagógico, **no** a las cuentas vulnerables de la aplicación original. Cada alumno tiene sus propios intentos y puntos en SQLite. El progreso vive en un volumen Docker y sobrevive a `stop`, `start`, `restart` y `down` sin `-v`.

El escritorio Kali es compartido por las cuentas del mismo Compose. El puntaje es individual, pero los archivos y ventanas del escritorio no son espacios privados. Para talleres simultáneos, cada alumno debe ejecutar su propio Compose en su equipo. Si varios alumnos se turnan en uno, deben cerrar sesión del portal y del cliente `lab`, o utilizar sesiones terminal separadas. Las semillas y modificaciones del target son compartidas: restablecer una contraseña en un ejercicio puede afectar al siguiente alumno.

## Abrir Kali y empezar a probar

En el portal, pulsa «Abrir Kali». Se abrirá noVNC con el escritorio XFCE. Si no conecta, revisa que el contenedor Kali esté saludable y que el navegador permita WebSockets. No necesitas conectar al puerto VNC nativo: solo se utiliza internamente en el contenedor.

Abre la terminal de Kali. Los nombres DNS `target`, `receiver`, `mailpit` y `academy` solo existen dentro de la red del laboratorio. `localhost` dentro de Kali es Kali, no el anfitrión ni VulnerableApp.

```bash
curl -i http://target:9090/VulnerableApp/
lab login
lab missions
lab status
```

Introduce las mismas credenciales que registraste en el portal. El CLI conserva el token únicamente en tu directorio de configuración de Kali con permisos restringidos. No copies tokens al chat ni a capturas públicas. Usa `lab --help` para ver las opciones exactas disponibles.

## Flujo de una misión

Primero lee el briefing y reconoce qué entrada controla el usuario, qué componente la interpreta y qué evidencia se espera. Ejecuta el comando de control benigno con `curl`; después, prueba el caso propuesto únicamente contra `target`. Mira el código HTTP, los encabezados y el cuerpo: un 200 no equivale a una vulnerabilidad.

Para que el portal vincule tu evidencia con tu cuenta, reproduce la solicitud mediante `lab request` usando el identificador exacto que aparece en la misión. `curl` directo permite aprender, pero **no entrega puntos**, porque no identifica de forma fiable al alumno. `lab request` pide al runner de Kali ejecutar la solicitud real y envía su resultado al verificador del servidor.

```bash
lab request commandInjection-02 --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

El identificador anterior sigue el formato del catálogo; utiliza siempre el mostrado en la misión por si el número cambia al regenerar el contenido. No uses una orden adicional ni sustituyas el marcador por un acceso al host. Los puntos se conceden una sola vez, aunque repitas la prueba. El portal actualiza el progreso al detectar nuevos intentos.

Los ejercicios sin verificador automático aparecen claramente como prácticas guiadas y no suman puntos. No declaramos explotación por la sola presencia de una cadena reflejada. En las misiones XSS que usan verificación de navegador, el runner abre un Chromium de entrenamiento dentro de Kali y comprueba el marcador DOM inocuo especificado; no roba cookies.

Para parámetros que contienen un NUL de entrenamiento, usa `--param-encoded` con `%00`, tal como el comando de la misión. El CLI decodifica el valor para enviarlo como JSON; el runner vuelve a codificarlo en la URL. No intentes colocar un NUL literal en argumentos de shell.

Abre VulnerableApp desde el acceso de Firefox dentro de Kali. El enlace del portal conduce al escritorio, no a la aplicación vulnerable en el mismo origen que tu sesión. Mailpit también se abre dentro de Kali.

## Usar Qwen como tutor

Selecciona la misión antes de preguntar. Solicita explicaciones sobre lo observado: «¿Por qué esta cabecera no prueba autenticación?» o «¿Qué diferencia hay entre el control y mi prueba?». El tutor responde en español y recibe solo el contexto del ejercicio actual.

Cuando propone una herramienta, el portal muestra la operación y sus argumentos. Revísalos y aprueba únicamente si corresponden al objetivo local. El modelo no dispone de shell libre y no controla la puntuación. Una herramienta del tutor ayuda a entender el resultado, pero no sustituye tu intento puntuable mediante `lab request`. Si Qwen rechaza una pregunta o no logra interpretarla, usa la guía estática: no se garantiza un modelo «sin restricciones».

Desde Kali también puedes usar `lab tutor msg --mission commandInjection-02 "Explica el control de esta misión"`. Para ejecutar una propuesta concreta ya mostrada, `lab tutor approve ID_PENDIENTE` expresa tu aprobación explícita. El CLI no inicia una shell del modelo.

## Pausar, conservar y restablecer

Para pausar conservando datos:

```console
docker compose stop
```

Para volver a empezar conservando el progreso:

```console
docker compose up -d
```

Para reiniciar las semillas H2 y el estado en memoria de la aplicación original, reinicia solo `target`. Esta acción no elimina los puntos del portal; sí puede invalidar sesiones y tokens creados durante los ejercicios:

```console
docker compose up -d --force-recreate target target-netlock
```

Descarga tu progreso JSON desde el portal antes de cualquier limpieza. `docker compose down -v` **borra** los volúmenes declarados, incluyendo progreso, escritorio y pesos locales. No lo uses para una pausa normal. Una exportación de progreso es un registro de evidencia, no una copia integral restaurable de SQLite y todos los servicios.
