# Harness del taller: aprender con comandos, evidencia y progreso

El escritorio Kali incluye el motor original [S1N6H/pentest-harness](https://github.com/S1N6H/pentest-harness), fijado al commit `4638f38082bdf37cea03ad151905c4bb8662f6e9`. El preset **Taller VulnerableApp** usa exclusivamente el Ollama del Compose y `huihui_ai/Qwen3.8-abliterated:27b`. No se necesita una cuenta de proveedor, una API key externa ni un Ollama instalado en el anfitrión. Una respuesta del modelo nunca sustituye la evidencia del servidor.

## 1. Entrar en el escritorio y en el agente

En la carpeta del repositorio, desde Windows, Linux o macOS:

```bash
docker compose up --build -d
```

Abrir `http://localhost:8080`, registrar una cuenta individual y pulsar **Abrir Kali**. En el escritorio noVNC, abrir **Harness del taller**. Si se prefiere una terminal de Kali:

```bash
firefox-esr http://127.0.0.1:2323
```

Aceptar la pantalla inicial del motor y, si solicita una carpeta, usar `/home/kali`. El preset predeterminado debe ser **Taller VulnerableApp**, no uno de pentesting genérico. No iniciar una segunda copia del servidor. Las explicaciones, razones de aprobación, catálogo y resultados docentes están en español; algunos controles del motor original aparecen como **Allow once**, **Reject** y **Choose workspace**: significan permitir una sola llamada, rechazarla y elegir la carpeta del trabajo.

El perfil 27B exige suficiente memoria en la VM de Docker. Los pesos tienen aproximadamente 18 GB de descarga y la inferencia requiere memoria adicional. El modelo usa el backend CPU dentro de Docker en Mac: no se presenta como una prueba de Metal ni se cambia a Ollama nativo de forma oculta. Consultar la guía de prueba del Mac y las medidas reales que acompañan esta versión.

## 2. Vincular la cuenta, sin entregar credenciales al modelo

En una terminal de Kali:

```bash
lab login
lab status
```

Usar la misma cuenta del portal. No pegar la contraseña, cookies ni tokens en el chat. La sesión del CLI queda en un archivo privado del usuario de Kali; el helper utiliza esa sesión para pedir evaluación a Academy. La clave del runner pertenece a otro usuario y no se entrega al agente.

Cada alumno debe usar su propia instancia Compose, o turnarse cerrando tanto la sesión del portal como la del CLI. El puntaje es individual por cuenta, pero el escritorio y el target son compartidos dentro de una misma instancia.

## 3. Qué puede hacer el harness

| Herramienta nativa | Operación real | Qué no autoriza |
|---|---|---|
| `lab_discover` | Resolver y comprobar los nombres/puertos fijos con Nmap TCP acotado. | No acepta IP, subred, puerto o destino arbitrarios. |
| `lab_missions` | Leer el catálogo público local; filtrar familia o consultar un ID exacto con paginación limitada. | No envía solicitudes, no lee archivos elegidos por el modelo y no concede XP. |
| `lab_http` | Ejecutar una solicitud al endpoint que fija la misión y mostrar respuesta/evidencia. | No sigue redirecciones ni concede puntos. |
| `lab_submit` | Pedir a Academy que reproduzca y evalúe el intento con el runner. | El modelo no calcula, cambia ni escribe el puntaje. |
| `lab_progress` | Consultar el progreso que Academy reporta para la cuenta iniciada con `lab login`. | No lee SQLite ni cuentas ajenas. |
| `skill` | Cargar uno de los tres skills docentes instalados. | No instala código, no modifica políticas y no abre herramientas genéricas. |

Todas las llamadas, incluso leer un skill o consultar progreso, requieren una aprobación nueva. El panel muestra la operación, misión, método y resumen acotado de argumentos; oculta valores de tipo credencial. Revisarlo antes de elegir **Allow once**. Un permiso anterior no se reutiliza. **Reject** impide ejecutar esa llamada; no autoriza al modelo a repetirla ni a usar otra herramienta para lograr lo rechazado.

## 4. Reconocer exclusivamente las máquinas del Compose

Enviar al chat:

> Carga vulnerableapp-scope. Después propón lab_discover con service all. Explica los nombres, IP, puerto y comando Nmap observados. No explotes nada y espera la aprobación de cada llamada.

`all` significa solo `target:9090`, `receiver:8081`, `mailpit:8025`, `academy:8000` y `ollama:11434`, no una subred ni otros proyectos Docker. Las IP cambian entre instalaciones. Un comando manual equivalente dentro de Kali es:

```bash
nmap -sT -n -Pn -sV --version-light -p 9090 target
```

El helper resuelve una IP de un nombre permitido y limita el reconocimiento. Si el fingerprint no termina, puede confirmar el mismo IP/puerto con otro Nmap TCP acotado. Un puerto abierto no implica que la versión esté identificada; leer ambos resultados sin atribuir un producto por una heurística de Nmap.

## 5. Elegir una misión sin adivinar su ID

Enviar:

> Carga vulnerableapp-http y consulta lab_missions con family sqlInjection y limit 8. Muéstrame cuáles son controles, cuáles tienen evaluación automática y qué evidencia requieren. No ejecutes solicitudes todavía.

Luego consultar un ID preciso, por ejemplo:

> Consulta lab_missions para mission_id sqlInjection-07. Explica su método, ruta fija, parámetros, criterio y mitigación. No asumas que un HTTP 200 demuestra el objetivo.

Las plantillas de la misión se leen del mismo catálogo versionado que usa el laboratorio. Si una plantilla contiene controles y payloads separados, seleccionar sus parámetros planos para cada solicitud; no mandar ambos diccionarios como un solo valor. Una práctica guiada/manual puede ser correcta sin conceder XP automático.

## 6. Hacer primero el control y después el cambio

Ejemplo de SQL ciega `sqlInjection-01`, práctica de contraste sin XP automático:

```bash
curl -sS --noproxy '*' --get --data-urlencode 'id=999' http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1
curl -sS --noproxy '*' --get --data-urlencode 'id=100 OR 2=2' http://target:9090/VulnerableApp/BlindSQLInjectionVulnerability/LEVEL_1
```

En el chat:

> Para sqlInjection-01, propón lab_http con method GET, params {"id":"999"}, headers {}, body null. Espera aprobación. Explica el resultado observado y después prepara, sin ejecutar aún, el cambio a {"id":"100 OR 2=2"}.

Comparar los cuerpos JSON y el comportamiento frente al control, no solo el código HTTP. La segunda solicitud requiere otra aprobación. El helper muestra el comando/solicitud acotados y el resultado que recibió: no rellenar una respuesta faltante con lo que el modelo espera ver.

## 7. Registrar un resultado con XP

Ejemplo de SSRF usando exclusivamente el receptor inocuo del Compose:

```bash
curl -sS --noproxy '*' --get --data-urlencode 'fileurl=http://receiver:8081/' http://target:9090/VulnerableApp/SSRFVulnerability/LEVEL_1
lab request ssrf-01 --method GET --param 'fileurl=http://receiver:8081/'
lab status
```

El `curl` directo sirve para entender la respuesta pero no identifica al alumno ni entrega XP. `lab request` y `lab_submit` piden evaluación a la misma API. En el chat:

> Carga vulnerableapp-evidence. Consulta la misión ssrf-01 y prepara una solicitud GET con params {"fileurl":"http://receiver:8081/"}, headers {} y body null. El destino debe ser únicamente receiver del Compose. Después del control observado propón lab_submit y espera aprobación. Informa solo success, XP concedido y score que devuelva Academy. Finalmente propón lab_progress para confirmar el estado de mi cuenta.

El resultado esperado del receptor contiene `VA_LAB_RECEIVER`, pero no darlo por observado antes de recibirlo. El evaluador comprueba sus condiciones; una misión lograda se premia una sola vez. Diferenciar XP de este intento y XP total. No repetir solicitudes para farmear puntos.

## 8. Otras familias y límites de la ayuda

Para inyección de comandos, usar solo el marcador benigno de la receta, como `printf VA_LAB_OK` en el target aislado; no introducir acciones contra el Mac, Internet u otras redes. Para XSS, usar el marcador DOM inofensivo: reflejar una cadena HTML no prueba ejecución; las misiones puntuables de navegador las verifica Chromium del runner. Para formularios, usar método, cuerpo y `content_type` reales sin duplicar query y formulario. XXE y SSRF deben apuntar únicamente a fixtures o receptor del laboratorio.

Las veinte familias y sus niveles están explicados en [TALLER.md](../TALLER.md). Algunas requieren razonamiento, herramientas manuales de Kali o evidencia de más de una solicitud; el harness no convierte una práctica manual en una validación automática. Tampoco recibe shell libre, herramientas de filesystem, búsqueda web, delegación o permiso para modificar su política.

## 9. Ver, conservar y terminar

```bash
lab status
lab export
lab logout
```

Cerrar también la sesión del portal en un equipo compartido. En el anfitrión, `docker compose stop` detiene servicios sin borrar datos. `docker compose down` conserva los volúmenes si no se usa `-v`. No borrar progreso y pesos con `down -v` salvo que esa destrucción sea deliberada.

## Comparar manual y harness de forma honesta

Usar el mismo nivel, parámetros y criterio en ambos caminos. Registrar el control, solicitud real, respuesta, evidencia y puntaje del servidor. Manual muestra dominio directo de las herramientas; harness añade consulta del catálogo, propuestas en lenguaje natural, revisión de argumentos y síntesis de resultados. No asumir que el agente es más rápido, que necesita menos aprendizaje o que nunca se equivoca. Las medidas de inferencia son del equipo y configuración documentados; no son tiempos de resolución para alumnos.

## Si el agente pregunta antes de mostrar el panel

A veces termina un turno con «¿apruebas el envío?» después de comparar las respuestas. Todavía no ha propuesto una llamada nativa. Responde en el chat: «Sí, revisé esta evidencia. Propón lab_submit de este ID con los mismos parámetros observados y espera Allow once; luego consulta lab_progress con otra aprobación». Esa confirmación didáctica **no sustituye** el nonce de ejecución. No apruebes otro ID o una solicitud que no hayas visto. Los pasos cortos son preferibles a pedirle resolver todo el capítulo de una vez.
