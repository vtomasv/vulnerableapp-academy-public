# Comenzar: Academy, Mercado Cordillera y Kali

Esta guía describe el recorrido local aprobado del laboratorio. Está escrita para una ejecución autorizada, con datos ficticios y una instancia propia de Docker Compose. No expongas el target, no uses túneles y no envíes pagos, credenciales reales ni solicitudes a servicios externos.

> Consulta [Validación y límites](VALIDACION.md) para distinguir los recorridos realmente probados de las prácticas guiadas. Este taller es una adaptación independiente basada en [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp) y [OWASP VulnerableApp](https://owasp.org/projects/vulnerableapp); conserva siempre sus [créditos](ATRIBUCION.md).

## 1. Mapa de las tres pantallas

| Pantalla | Dónde se abre | Para qué sirve |
|---|---|---|
| **Academy / portal** | En el anfitrión: `http://localhost:8080`. Dentro de Kali: `http://academy:8000`. | Registrar la cuenta pedagógica, elegir `commandInjection-02`, leer el criterio y consultar el XP. |
| **Mercado Cordillera / VulnerableApp** | Se abre desde **Abrir tienda vía Kali** en Academy, que lleva al noVNC de Kali; Firefox dentro de Kali usa `http://target:9090/VulnerableApp/mercado/`. | Tienda ficticia para ambientación y ejercicios. Es un origen aislado del portal y no tiene pagos reales. |
| **Kali / harness** | Se entra con **Abrir Kali** desde Academy. El icono del escritorio abre `http://127.0.0.1:2323` dentro de Kali. | Terminal, Firefox/Chromium, `lab` y asistencia acotada con una aprobación nueva por llamada. |

La ruta técnica original se conserva como referencia opcional dentro de Kali en `http://target:9090/VulnerableApp/original/`. Si aparece su selector de idioma inglés, es el selector legacy del upstream: no es un error ni indica que falte una aplicación moderna. La personalización del launcher no sustituye el motor original, que permanece intacto. La pantalla original y la captura heredada pueden conservar textos técnicos en inglés porque pertenecen al legado de SasanLabs; las instrucciones nuevas de este proyecto están en español. No se promete traducir todos los textos técnicos del upstream.

**Importante sobre `localhost`:** `target:9090` y `academy:8000` son nombres de la red interna del laboratorio. Desde el Mac o el PC no intentes abrir el target, la tienda ni el harness: no se publica el puerto de host `8081` ni el puerto `2323`. Compose publica solo el gateway en `127.0.0.1:8080`; usa las rutas `target:9090` y `academy:8000` solamente dentro de Kali.

## 2. Arrancar y registrar una cuenta

1. Clona el repositorio o descarga el ZIP completo. Con Git:

   ```console
   git clone https://github.com/vtomasv/vulnerableapp-academy-public.git
   cd vulnerableapp-academy-public
   docker compose up --build -d
   ```

2. Abre `http://localhost:8080` en el navegador del anfitrión y registra una cuenta **individual** de Academy. Esta cuenta pertenece al portal pedagógico; no es una cuenta de la aplicación vulnerable.
3. Pulsa **Comenzar taller**: selecciona automáticamente `commandInjection-02`, la práctica de soporte diagnóstico. También puedes abrir Academy con `http://localhost:8080/#mission=commandInjection-02`. Lee el control, la solicitud esperada y el criterio antes de ejecutar nada.
4. Pulsa **Abrir Kali** cuando necesites la terminal o el escritorio. Para la tienda, **Abrir tienda vía Kali** debe llevarte al noVNC del gateway: `http://localhost:8080/kali/vnc.html?autoconnect=1&resize=scale&path=websockify`. Desde Kali, Academy se consulta como `http://academy:8000`.
5. En una terminal de Kali, inicia el cliente con la misma cuenta del portal:

   ```bash
   lab login
   lab status
   ```

   `lab login` guarda una sesión local restringida para el usuario de Kali. No pegues la contraseña, cookies, tokens ni claves en el chat del modelo ni en capturas públicas.

### Abrir Mercado Cordillera desde Kali

Compose no publica un puerto de host para la tienda. En el escritorio noVNC abierto desde Academy, usa Firefox y pulsa el icono **Mercado Cordillera**; la URL interna correcta es:

```text
http://target:9090/VulnerableApp/mercado/
```

Mercado Cordillera es una ambientación comercial chilena ficticia, con precios ilustrativos y carrito local. No procesa pagos, no debe recibir datos de tarjeta y no debe confundirse con un comercio real. El origen de la tienda se mantiene separado del origen de Academy para que la práctica no comparta cookies ni sesión con el portal.

## 3. Rutas desde Kali

Usa Firefox dentro de Kali para abrir estas direcciones:

```text
Academy:       http://academy:8000
Tienda:        http://target:9090/VulnerableApp/mercado/
Original:      http://target:9090/VulnerableApp/original/
Harness:       http://127.0.0.1:2323
```

La tienda no tiene enlace ni puerto propio en el anfitrión: se abre mediante el noVNC del gateway y el icono de Firefox en Kali. Las solicitudes técnicas de las misiones se hacen contra `target:9090` desde Kali. Para volver desde Kali al gateway, abre `http://gateway:8080/`. La página de GitHub Pages no aloja ninguno de estos servicios: es una landing estática con documentación y capturas locales.

## 4. Recorrido manual puntuable: `commandInjection-02`

En Academy pulsa **Comenzar taller**. En la tienda, **Retos del taller** muestra el mismo ID `commandInjection-02` como soporte diagnóstico. Esta práctica enseña a separar control, prueba y evidencia. El parámetro real es `ipaddress` y la ruta del nivel es `CommandInjection/LEVEL_1`.

### 4.1 Control benigno

Desde la terminal de Kali, inicia primero la misma cuenta del portal y envía el control:

```bash
lab login
curl -sS --noproxy '*' --get \
  --data-urlencode 'ipaddress=127.0.0.1' \
  http://target:9090/VulnerableApp/CommandInjection/LEVEL_1
```

Lee la respuesta completa y conserva el control como referencia. Que la respuesta tenga HTTP 200 no demuestra una inyección: el código HTTP por sí solo no es el criterio.

### 4.2 Prueba benigna acotada

La prueba permitida usa únicamente el marcador interno indicado por la misión:

```bash
curl -sS --noproxy '*' --get \
  --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK' \
  http://target:9090/VulnerableApp/CommandInjection/LEVEL_1
```

Compara la respuesta real con el control y comprueba que el resultado de la prueba contiene `VA_LAB_OK`. No añadas órdenes, archivos, redirecciones, destinos de red ni efectos sobre el host. No afirmes que `ping` esté permitido, que exista ejecución arbitraria general o que un HTTP 200 baste: el criterio es el marcador benigno indicado.

### 4.3 Registrar el intento y comprobar el XP

El `curl` directo sirve para aprender y observar, pero no identifica tu cuenta ni concede XP. `lab request` crea un intento autenticado en Academy (`http://academy:8000`) con el ID exacto, método, parámetros, headers, cuerpo y tipo de contenido. Registra la misma solicitud así:

```bash
lab request commandInjection-02 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'
lab status
```

La misión entrega **100 XP una sola vez** cuando Academy valida la evidencia del runner de Kali. `lab status` muestra el progreso de la cuenta; repetir una misión ya lograda no duplica su recompensa. Un `curl` sin `lab request`, navegar, una visita a la tienda, una respuesta del modelo o un HTTP 200 no otorgan puntos.

## 5. Recorrido con harness: soporte diagnóstico acotado

El harness es una ayuda acotada, no una shell libre ni un sustituto del análisis manual.

1. Si llegaste desde **Abrir tienda vía Kali**, el gateway muestra el noVNC con `autoconnect=1`, `resize=scale` y `path=websockify`. En el escritorio XFCE de Kali, abre el icono **PentestHarness / Harness del taller**. El acceso abre `http://127.0.0.1:2323` en el navegador **dentro de Kali**. No abras ese `127.0.0.1` esperando encontrarlo en el navegador del anfitrión: no existe un enlace ni un puerto host `2323`.
2. Usa el preset **Taller VulnerableApp**. En una terminal de Kali, ejecuta `lab login` con la misma cuenta que registraste en Academy. El modelo no necesita ni debe recibir esa contraseña, el token del CLI o una cookie.
3. En Academy pulsa **Comenzar taller** o abre el ID `commandInjection-02`; en la tienda está en **Retos del taller**. Pide primero el catálogo y el control, por ejemplo:

   > Carga `vulnerableapp-http` y consulta `lab_missions` para `commandInjection-02`. Explica su método, ruta, control y criterio. No envíes todavía una solicitud y espera la aprobación de cada llamada.

4. Carga **`vulnerableapp-evidence`** para el envío y revisa cada panel de aprobación. `skill`, `lab_missions` (consulta acotada del catálogo), cada `lab_http` permitido, `lab_submit` con evidencia y `lab_progress` requieren una **aprobación nueva**. **Allow once** autoriza solamente esa llamada; **Reject** la rechaza y no se convierte en autorización para repetirla o cambiar de herramienta.
5. Solicita un control con `lab_http` usando `GET`, ruta fija `CommandInjection/LEVEL_1` y `ipaddress=127.0.0.1`. Después, en otra llamada y con otra aprobación, usa únicamente el marcador benigno:

   ```text
   ipaddress=127.0.0.1|printf VA_LAB_OK
   ```

6. Comprueba que la respuesta de la prueba contiene `VA_LAB_OK` y que el control no lo contiene. Luego pide `lab_submit` para el mismo ID y los mismos parámetros; aprueba esa llamada solo si el panel coincide con lo que revisaste. Finalmente pide `lab_progress` con una aprobación aparte.

Este caso comprueba un marcador acotado en `content`; puede haber otros textos o errores en la respuesta. **No afirmes que ping esté permitido**, que haya una ejecución arbitraria general o que un HTTP 200 baste: el criterio solo es el marcador benigno indicado. No añadas órdenes, archivos, redirecciones, destinos de red ni efectos sobre el host. `commandInjection-02` vale **100 XP una sola vez** cuando Academy recibe y valida la evidencia. La cuenta ficticia de Mercado Cordillera no sirve para iniciar sesión en Academy.

## 6. Qué puntúa y cómo conservar la identidad

La puntuación solo nace de un intento autenticado de `lab request` o del envío aprobado equivalente del editor/harness (`lab_submit`). `lab_http` muestra la solicitud y la respuesta, pero no concede XP; `curl` directo tampoco. El modelo puede explicar, consultar el catálogo y proponer operaciones, pero no calcula ni escribe el puntaje.

La cuenta de Academy y la sesión iniciada con `lab login` deben ser la misma. Si varias personas se turnan en una instancia, cierren sesión en el portal y en `lab`, o usen instancias separadas: el escritorio y el target son compartidos aunque el progreso sea individual. Nunca compartas contraseñas con el modelo.

Para pausar sin borrar datos:

```console
docker compose stop
docker compose up -d
```

No uses `docker compose down -v` para una pausa: elimina progreso, escritorio, receptor y pesos locales.

## 7. GitHub Pages, capturas y límites

La página pública es una landing estática. No ejecuta Academy, no publica el target, no ofrece el harness, no conecta con Ollama y no convierte `localhost` en un servicio remoto. Para ejecutar el laboratorio hay que clonar el repositorio y arrancarlo localmente con Compose; la landing enlaza al repositorio, a esta guía y a las demás referencias.

Las capturas nuevas del recorrido se incorporan como archivos locales, no desde CDN:

- `site/assets/academy-inicio.png`
- `site/assets/mercado-cordillera.png`

Son capturas del recorrido real; las referencias históricas se conservan y se identifican por separado. Para volver a tu sesión del Mac, usa la pestaña de Academy original. Si abres Academy dentro de Firefox Kali por `gateway:8080`, inicia sesión allí con la misma cuenta; la tienda no transporta tokens entre orígenes.

Trabaja únicamente con el alcance del Compose y datos ficticios. No publiques puertos, no uses túneles, no pruebes otros proyectos ni envíes solicitudes fuera del receptor local autorizado.

## 8. Actualizar sin perder progreso

Conserva la carpeta, el nombre del proyecto Compose y tu `.env`. Ejecuta `git pull --ff-only` y `docker compose up --build -d`; no elimines los volúmenes. Recarga una pestaña antigua si conserva la interfaz anterior. El gateway devuelve `Cache-Control: no-store` y los assets de Academy están versionados.
