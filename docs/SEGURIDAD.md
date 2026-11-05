# Seguridad y alcance del laboratorio

VulnerableApp es vulnerable intencionalmente. El aislamiento debe acompañar a las reglas del taller: solo cuentas de entrenamiento, ningún dato personal, ningún acceso a sistemas de terceros y ninguna exposición pública. Las URLs de las prácticas apuntan a servicios Docker de este proyecto.

## Qué se protege y qué no

El gateway publica un único puerto en loopback del anfitrión. Los servicios internos no publican puertos adicionales; no se monta el socket de Docker, el home del host, dispositivos ni el sistema de archivos del anfitrión. El escritorio Kali no tiene sudo y el runner usa una identidad Unix distinta.

Las redes Docker internas reducen la salida hacia otras redes. No confundir una red `internal: true` con una garantía de bloqueo de toda comunicación posible con el anfitrión: el gateway del bridge y diferencias entre motores requieren pruebas específicas. Consulta la implementación de las reglas de salida en Compose y los scripts de smoke test. No afirmamos aislamiento perfecto ante una vulnerabilidad del kernel, del motor Docker o un escape de Chromium; para prácticas avanzadas, usa una VM desechable como barrera adicional.

Los servicios temporales de construcción y descarga del modelo necesitan Internet. El servidor Ollama de inferencia funciona después en una red interna. No sustituyas su URL por un proveedor externo ni añadas `host.docker.internal` a los destinos permitidos del harness.

El gateway necesita una red `ingress` no interna para que Docker publique localhost. Solo el gateway se conecta a ella; `gateway-netlock` comparte únicamente su namespace de red y aplica OUTPUT DROP, loopback, respuestas establecidas y tres destinos internos fijos. IPv6 está deshabilitado y el DNS externo se desvía a una dirección de documentación. El usuario del gateway y el alumno no reciben NET_ADMIN.

## Harness del tutor

El tutor Qwen recibe el contexto de una misión y puede proponer herramientas concretas. El alumno ve y aprueba la propuesta antes de que se ejecute. El servidor vuelve a verificar el usuario, la misión, la operación, los límites y la vigencia de la aprobación. Aprobar una herramienta no le otorga una shell ni permisos para conceder puntos.

El runner dentro de Kali autentica las llamadas con una clave de servicio que no se entrega al escritorio. Construye argumentos sin `shell=True`, fija el origen HTTP del target y no acepta un host arbitrario. Rechaza caracteres de control, cabeceras de enrutamiento peligrosas y herramientas no incluidas en la lista. Aplica límites de tiempo, de cuerpo y de respuesta. Las redirecciones no se siguen automáticamente.

La prueba de navegador, cuando una misión la necesita, ejecuta una rutina fija sobre el target y consulta un marcador DOM benigno. No acepta un programa JavaScript libre del modelo ni permite leer cookies del alumno. El navegador de prueba es efímero. Que Chromium use una configuración de contenedor no equivale a una sandbox de seguridad completa: el contenedor y las reglas de red son parte de la defensa.

La salida de VulnerableApp y de las herramientas es **no confiable**. Puede contener una instrucción de prompt injection: se presenta al modelo como evidencia, no como autorización para modificar las reglas. La defensa principal no es el prompt, sino la validación externa de herramienta y destino.

## Harness original dentro de Kali

Kali incluye el motor **S1N6H/pentest-harness**, fijado al commit documentado, con el preset **Taller VulnerableApp** y tres skills locales. Solo expone `lab_discover`, `lab_missions`, `lab_http`, `lab_submit`, `lab_progress` y `skill`; cada invocación exige una aprobación nueva. La guarda monotónica rechaza herramientas fuera de la lista, argumentos fuera del schema y llamadas sin el servicio de aprobación. No se habilitan herramientas genéricas de shell, filesystem, búsqueda web o delegación.

`lab_discover` resuelve cinco nombres Docker y usa argv Nmap fijos. Un fingerprint que agota su límite puede dar paso a una segunda comprobación TCP Nmap del mismo IP y puerto; esto no inventa la versión. `lab_http` usa rutas del catálogo, sin redirects y con límites de tamaño. `lab_submit` usa la sesión privada de `lab login` para pedir evaluación: no puede escoger XP ni escribir la base de puntajes. El harness corre como `kali` (UID 1000), mientras el runner conserva UID 1001 y su clave inaccesible al alumno.

La API del harness y el adaptador de Ollama no publican puertos al anfitrión. Se usan desde Firefox en el escritorio noVNC. El adaptador fija un único modelo y servidor local, desactiva thinking y limita generación, contexto e hilos. Ninguna API key externa se copia al contenedor.

## Verificación y puntaje

El puntaje se calcula en el servidor a partir de evidencia producida por el runner, ligada a la identidad autenticada del alumno. El navegador y el CLI no pueden elegir cuántos puntos vale una prueba ni cambiar su criterio. Una restricción única en la base de datos evita conceder la misma recompensa varias veces por concurrencia o repetición.

No se otorgan puntos por abrir una página, hacer clic en «completar», pegar un resultado fabricado o porque Qwen afirme que hubo éxito. `curl` directo no suma puntos por falta de atribución. Para puntaje, usa el intento autenticado mediante `lab request` o envía tus propios parámetros desde el editor de la tienda.

Una misión declara el hecho preciso que observa. `contains` se refiere al cuerpo o a un campo JSON, nunca al texto del comando enviado. La evidencia XSS puntuable proviene del DOM del navegador de prueba, no del reflejo en el body. Un status 200 no prueba IDOR; un HIT de caché aislado tampoco prueba que otro visitante recibió el contenido controlado. Los ejercicios que todavía requieren correlación manual se mantienen como guía sin puntaje automático.

Esto es una plataforma de aprendizaje, no una plataforma anti-trampas ni un examen supervisado. El alumno conoce los criterios, puede leer el código y dispone de ejemplos resueltos. El operador del anfitrión tiene control sobre Docker y los volúmenes; no se intenta impedir que modifique su propio laboratorio. Las cuentas separan progreso, no el escritorio compartido ni la base del target.

## Privacidad y copias

Las conversaciones con Qwen permanecen en los servicios locales. Los registros del laboratorio pueden contener parámetros, tokens de entrenamiento y cuerpos de evidencia; no uses credenciales reales. Los volúmenes de Docker no están cifrados por esta aplicación: el cifrado del disco y sus copias corresponden al anfitrión.

No publiques `.env`, la clave del harness, bases SQLite, sesiones del CLI ni volúmenes. Este repositorio de código es público por autorización del propietario; las claves y datos se generan localmente y no se incluyen en Git. Las licencias y commits fijados permiten auditar la aplicación y el harness original.
