# Validación y límites de prueba

## Resultados comprobados en esta implementación

La aplicación Java original se compiló con Java 17 y `./gradlew bootJar -x test` a partir del commit `4df80bbcd42682ecf26334f12c568e0f4a326c1a`. Se arrancó una distribución expandida equivalente a la del Dockerfile, con las fixtures del taller. No se ejecutó la suite completa de tests del proyecto upstream: no se afirma que todos esos tests hayan pasado.

Se ejecutaron **95 objetivos** del catálogo mediante la cadena real **API Academy → runner auténtico → curl/Chromium → target Java**, y los 95 cumplieron su criterio. También se recuperaron y verificaron los **8 retos criptográficos de niveles 2–9** de la instancia actual con los cálculos locales de `lab-crypto`, sumando **103 objetivos puntuables distintos comprobados**. El nivel 10 estaba incluido entre los primeros 95. El nivel criptográfico 1 conserva su criterio real de contraseña correcta, pero no se resolvió en esta validación: requiere inspeccionar la base de entrenamiento como indica la guía.

La prueba inicial de recetas HTTP directas detectó diferencias de formularios duplicados, codificación, expansión XML y filtros XSS. Se corrigieron las recetas reproducibles; las que no demostraron el hecho esperado quedaron explícitamente manuales y con 0 XP. El estado final del catálogo es **104 prácticas puntuables y 85 guiadas/manuales**, no 189 exploits automáticamente verificados.

`pytest -q tests/test_backend.py` pasó **10 pruebas** de autenticación, cuentas separadas, idempotencia de puntaje, bloqueo de puntaje manual, controles, caché en varias solicitudes, validación de navegador, límites, exportación con más de 20 completados, aprobación de herramientas, extracción nativa de llamadas Ollama y rutas de assets. La suite usa mocks para pruebas unitarias de runner/modelo; no debe confundirse con una inferencia real de Qwen. Se observó un warning de compatibilidad/deprecación Starlette/httpx; no impidió ejecutar la suite.

Se verificó con una cadena real que el primer intento correcto entrega 100 XP, repetirlo entrega 0 XP adicionales y otra cuenta permanece en 0. El runner rechaza solicitudes sin la clave de servicio con HTTP 401. La exportación mantiene todos los identificadores completados, en vez de recortar listas a veinte entradas.

Se comprobó sintaxis Python, JavaScript y shell. El manifiesto se validó con el parser real de Compose v2 mediante `docker compose config --quiet`, sin arrancar un daemon. La prueba funcional del portal utiliza Chromium y Playwright 1.64.1: registra un alumno, envía un JSON explícito, observa 100 XP y comprueba el catálogo y cierre de sesión. La prueba completa de UI terminó sin errores JS ni desbordamiento horizontal a 390 px de ancho; también validó cierre de sesión. Las capturas están en `docs/images/`; consulta `tests/ui_smoke.py` para repetirla.

## Lo que no se probó aquí

**No había un motor Docker disponible en este entorno.** No se ejecutó `docker compose up` de todo el stack, ni builds de todas las imágenes, ni el escritorio XFCE/noVNC real dentro de Kali. No se verificaron las reglas iptables en contenedores, la descarga de pesos de Ollama, la inferencia real del modelo seleccionado ni la compatibilidad de Docker Desktop en Windows/macOS o todas las arquitecturas.

No se afirma aislamiento perfecto frente a escapes de contenedores, canales DNS, vulnerabilidades del kernel, del navegador o diferencias de Docker. Las reglas y redes están implementadas; falta su verificación de runtime en el equipo de destino. La variante Qwen3 ablacionada y su etiqueta se verificaron en la ficha pública del autor, no mediante un benchmark de calidad de respuestas.

## Comprobaciones que debe realizar el instructor

Antes del aula, valida la configuración y arranca una instalación limpia:

```console
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 init model-init target-netlock lab-netlock target kali academy ollama gateway
```

Los inicializadores deben terminar con exit code 0. Los servicios residentes deben quedar healthy. Kali comprueba runner, página noVNC y VNC local. Abre el portal, crea una cuenta, conecta el escritorio y abre Firefox hacia target. Verifica Mailpit y que Qwen responde antes de ofrecerlo en clase.

Desde el anfitrión comprueba los servicios desde dentro de Kali:

```console
docker compose exec --user kali kali lab doctor
docker compose exec kali curl -fsS http://target:9090/VulnerableApp/
docker compose exec kali curl -fsS http://127.0.0.1:6080/vnc.html
docker compose exec kali curl -fsS http://ollama:11434/api/tags
docker compose exec lab-netlock iptables -S OUTPUT
docker compose exec target-netlock iptables -S OUTPUT
```

El modelo listado debe coincidir con OLLAMA_MODEL. Prueba una conversación y una propuesta que se ejecute solo tras aprobarla. No simules respuestas si el modelo no está disponible: el portal devuelve un error real y la guía estática permanece utilizable.

En Linux/macOS o WSL, `sh scripts/smoke.sh` ejecuta comprobaciones de servicios, escritorio y reglas. Una conexión HTTP fallida a un gateway no basta como prueba de aislamiento; revisa también OUTPUT DROP, destinos explícitos, IPv6, DNS y la política del anfitrión. No elimines restricciones para que una prueba aparentemente pase.

Registra dos alumnos y repite la misión `commandInjection-02`: el primero obtiene puntos una sola vez y el segundo conserva su progreso propio. Descarga el JSON, reinicia Academy y verifica que el progreso sigue allí. Revisa las familias con estados compartidos por separado; cada alumno debe usar su propio Compose para sesiones simultáneas.

Para volver a crear el target y su namespace de firewall utiliza `docker compose up -d --force-recreate target target-netlock`. Para recrear Kali, inclúyelo junto a `lab-netlock`. No hagas `down -v` como rutina de pausa: borra progreso, escritorio, correo y pesos locales.

## Repetir pruebas de desarrollo

Las pruebas Python se incluyen como herramientas de desarrollo, no como instalación requerida en el anfitrión del alumno. `integration_stack.py` espera Academy y el runner reales, y solo admite API local o el nombre Docker academy. `integration_catalog.py` es una prueba auxiliar HTTP y no reemplaza el verificador de producción; su modo localhost transforma algunas URLs del receptor, por lo que ciertas comparaciones de Location difieren respecto del laboratorio. La cadena real `integration_stack.py` es la referencia de los 95 objetivos.
