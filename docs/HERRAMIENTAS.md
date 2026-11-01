# Herramientas dentro de Kali

Todas las herramientas de práctica viven en la imagen Kali. El anfitrión solo usa Docker y un navegador. Tener una herramienta instalada no implica permiso para apuntarla a otra red: el único target del taller es `target:9090` y los únicos receptores auxiliares son los servicios declarados en Compose.

## Terminal y HTTP con curl

`curl` permite ver exactamente qué envías. `-i` imprime los encabezados junto al cuerpo; `--get` coloca los datos en la query; `--data-urlencode` evita que comillas, espacios y símbolos modifiquen la estructura HTTP. No uses `-L` salvo que la guía indique un recorrido local concreto: seguir una redirección cambia lo que estás observando.

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_1 \
  --data-urlencode 'ipaddress=127.0.0.1'
```

El control es una petición normal. Para estudiar el marcador de inyección, cambia únicamente el parámetro y conserva la ruta:

```bash
curl -i --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_1 \
  --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK'
```

El efecto esperado se limita a imprimir `VA_LAB_OK`. No añade persistencia, conexiones de retorno, acceso a secretos ni comandos destructivos. La salida de `ping` puede variar; observa el campo `content`, no solo `isValid` ni el 200.

## Leer y comparar JSON con jq

`jq` selecciona campos y hace comparaciones claras. Un `content` puede ser una cadena o un objeto según la familia; inspecciona el tipo antes de acceder a propiedades. Si contiene un JSON codificado como cadena, `fromjson` lo convierte en un objeto.

```bash
curl -sS --get http://target:9090/VulnerableApp/CommandInjection/LEVEL_1 \
  --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK' | jq .
```

Puedes guardar controles en archivos de tu directorio de Kali para compararlos. No uses rutas del host ni cargues datos reales al laboratorio.

## Cliente lab: identidad, evidencia y puntaje

`lab` es el cliente propio del taller. En vez de confiar en un resultado que el alumno pegó, solicita al runner de Kali realizar la petición y entrega al servidor el resultado observado. La ruta y los criterios provienen del catálogo de la misión, no del cliente ni del modelo.

```bash
lab --help
lab login
lab missions
lab status
```

Copia el `lab request` exacto mostrado en la misión, y modifica sus argumentos para practicar. Usa comillas simples cuando el payload contenga `$`, `!` o `#`; una comilla simple dentro del valor requiere una combinación de comillas adecuada. El tutorial incluye los comandos ya escapados.

Los puntos son una medida de hitos de aprendizaje, no una evaluación anti-trampas: el código, los ejemplos y los criterios están disponibles para aprender. Tampoco acreditan por sí solos una explotación general; por ejemplo, un encabezado Location demuestra una decisión de redirección, no que alguien haya visitado un sitio de phishing.

## Firefox y las herramientas del navegador

Abre Firefox **dentro de Kali** y navega a `http://target:9090/VulnerableApp/`. Usa F12 para inspeccionar Network, Console y DOM. Network permite comparar la ruta real, los parámetros, el método y la respuesta de la aplicación. Console sirve para observar errores, no para pegar código que no comprendes.

En XSS, diferencia el texto reflejado del código ejecutado. Los ejemplos del taller usan exclusivamente un atributo `document.body.dataset.vaLab` como marcador de entrenamiento. Las misiones con prueba automática de navegador abren Chromium en el runner y consultan ese marcador con una expresión fija. Los ejemplos persistentes que requieren varias peticiones pueden permanecer como prácticas manuales sin puntaje automático; se indica en cada misión.

## OWASP ZAP

ZAP está incluido como dependencia obligatoria; ábrelo desde la terminal de Kali:

```bash
zaproxy
```

Crea una sesión temporal. Define un contexto que incluya exclusivamente `http://target:9090/VulnerableApp/.*` y marca ese contexto como in scope. Usa Protected Mode. Configura el proxy manual de Firefox con HTTP `127.0.0.1` y puerto `8080`; esa dirección es el proxy ZAP **de Kali**, no el puerto del portal del anfitrión.

Primero observa peticiones manuales con el escaneo pasivo. En History, abre una petición y compara Request/Response con `curl`. El Repeater/Request Editor permite repetir una petición cambiando una sola variable. No hagas un escaneo activo de toda la red ni actives pruebas de denegación de servicio. El puntaje del portal no proviene del número de alertas de ZAP: cada misión requiere su evidencia específica mediante el cliente `lab`.

Si ZAP no aparece, verifica las dependencias de la imagen y la disponibilidad del paquete para la arquitectura de tu equipo; no descargues herramientas en el anfitrión como solución. Se documentan las comprobaciones reales en `VALIDACION.md`.

## sqlmap y nmap

Estas herramientas están orientadas a comprobaciones muy acotadas, no a descubrir objetivos fuera del laboratorio. El tutorial manual de SQL explica primero la consulta y sus controles; no necesitas extracción automática de bases de datos ni acceso a archivos.

Para inventariar únicamente el puerto conocido de la aplicación, sin raw sockets:

```bash
nmap -sT -Pn -p 9090 target
```

No uses rangos de red, detección masiva, scripts contra el host ni opciones de explotación. `-sT` usa conexiones TCP ordinarias y no requiere conceder NET_RAW a Kali. Para comprobar la instalación de sqlmap:

```bash
sqlmap --version
```

El workshop no entrega puntaje por lanzar sqlmap ni por una alerta de scanner. Usa el comportamiento de las consultas del catálogo como verdad del ejercicio y no exportes datos fuera del contenedor.

## Mailpit: OTP y restablecimiento de contraseña

Mailpit captura los correos del target local y evita enviar mensajes a destinatarios reales. Abre `http://mailpit:8025/mailpit/` desde Firefox en Kali o el enlace del portal. Identifica el email de prueba de la guía, abre el mensaje y examina el token o enlace generado. Son datos ficticios y no deben reutilizarse en servicios reales.

No copies al tutor todos los correos ni todos los tokens de otros alumnos. Observa si el token caduca, si se invalida después de usarse y si queda vinculado a una identidad. Cuando el ejercicio requiere dos estados o una espera, la guía distingue esa práctica de un verificador HTTP de una sola respuesta.

## OpenSSL, Python y LDAP

`openssl` ayuda a inspeccionar hashes, codificación y claves **de laboratorio**, y Python permite procesar respuestas sin un servicio externo. No hace falta romper hashes de terceros. `ldapsearch` trabaja únicamente contra el LDAP embebido del target cuando el módulo lo habilita; los ejercicios de inyección LDAP del catálogo usan su endpoint HTTP para mantener el mismo flujo de la aplicación.

```bash
openssl version
python3 --version
ldapsearch -VV
```

No cambies el harness para convertir estos programas en una shell automática abierta al modelo. La práctica manual del alumno y la automatización del tutor tienen permisos diferentes: el tutor solo ve las herramientas estructuradas y acotadas publicadas por el runner.

## Criptografía local sin servicios externos

Después de intentar el reto, ejecuta `lab-crypto 2` para ver Base64, `lab-crypto 3` para César o `lab-crypto 5` para comparar MD4 con las diez semillas públicas del commit. La ayuda solo acepta los niveles 2–10 y solo consulta target. No usa diccionarios externos ni fuerza bruta en red. Sin `--submit` no registra puntos; con `--submit` envía el resultado mediante tu sesión `lab`.
