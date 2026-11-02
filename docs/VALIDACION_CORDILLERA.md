# Validación de Mercado Cordillera — 2026-11-02

Esta revisión se realizó en el Mac Apple M3 Max / 128 GB del facilitador con el laboratorio real de Docker Compose. Las pantallas públicas son documentación estática, no un target en Internet.

## Recorrido manual y UI

Desde el navegador del Mac, Academy seleccionó `commandInjection-02` al pulsar **Comenzar taller**. **Cargar control** y enviar dejó la cuenta en **0 XP**. **Cargar marcador benigno** y enviar produjo `VA_LAB_OK` en el `content` real del endpoint y **100 XP** en Academy. También se abrió noVNC y se vio Mercado Cordillera dentro de Firefox Kali, no en el origen del portal.

`tests/cordillera_ui_e2e.py` pasó con Chromium dentro de Kali y una cuenta ficticia nueva: selección inicial, control negativo, prueba positiva, 100 XP, conexión real del editor de tienda al endpoint, selector de 20 familias y 189 misiones, retorno con ID de misión, backoffice pedagógico y disponibilidad del original. Comprobó ausencia de overflow en Academy y tienda a 390, 768, 1200, 1440 y 1512 px, sin errores de página. Esto no equivale a resolver automáticamente las 189 prácticas.

## Harness y modelo

El modelo del Compose fue `huihui_ai/Qwen3.8-abliterated:27b`, mediante Ollama local, sin replay ni sustitución por un modelo remoto. El caso usa una cuenta ficticia diferente y limita los paneles a la skill de evidencia, el catálogo del ID exacto, el `lab_submit` con `ipaddress=127.0.0.1|printf VA_LAB_OK` y la lectura de progreso. Academy, no el texto del modelo, es la fuente de XP. Las aprobaciones de QA son acciones automatizadas condicionadas a los argumentos concretos del caso; en clase las realiza el estudiante con **Allow once**.

**Resultado final: PASS, 100 XP**, con cuatro paneles distintos observados y aprobados para `skill`, `lab_missions`, `lab_submit` y `lab_progress`, sin errores de página. Se confirmó la misión en el API autenticado de Academy. Es una prueba acotada de este recorrido: no afirma resolver todo el catálogo ni que el modelo nunca necesite orientación.

## Regresión y conservación

Se ejecutaron **10 pruebas de backend con pytest** (con mocks donde el test los declara) y **22 controles del helper real** dentro de Kali: 22 PASS, 0 FAIL, 0 SKIP. Cubren puertos internos, rechazo de destinos externos, cabeceras/rutas no autorizadas, capabilities del alumno, sesión y evidencia/XP individual. La allowlist de herramientas no se amplió.

Antes de actualizar se conservó un respaldo SQLite privado y una referencia de hashes por fila. Después, todos los hashes de filas anteriores continuaban presentes. Se reutilizaron los volúmenes existentes; no se utilizó `down -v` ni se eliminaron cuentas o pesos.

## Problemas detectados y corregidos

- Spring no servía un índice de directorio para `/mercado/` ni `/original/`. Se añadieron dos rutas de entrada en `target-overlay/AcademyNavigation.java`, separadas de `vendor/`. No se cambió ningún controlador vulnerable upstream.
- El navegador conservaba HTML/JS anteriores. Se versionaron los assets de Academy y el gateway usa `Cache-Control: no-store`.
- El firewall de Kali impedía volver al gateway. Se permitió exclusivamente el servicio interno `gateway:8080` para navegación; los cinco destinos de las herramientas siguen siendo los originales. El target no comparte origen ni publica puerto propio.
- Las pruebas concurrentes alcanzaron el límite de 512 procesos/hilos de Kali: el cgroup registró 47 denegaciones y aparecieron `EAGAIN` y `can't start new thread`. Se mantuvo un límite finito de 1024 y se añadió `init: true`; no se concedieron nuevas capabilities ni se reinició el Mac.
- Algunos intentos de QA se interrumpieron por selectores ambiguos o permisos del archivo copiado, no por un XP positivo. Se corrigieron y repitieron; no se presentan esos intentos como ejecuciones verdes.

## Alcance

Solo el gateway publica `127.0.0.1:8080`. Target, Ollama, runner y puerto nativo del harness no se publican al host. La interfaz técnica original conserva textos ingleses como referencia opcional; la tienda y el inicio docente están en español. La vitrina, carrito, clientes y backoffice son ficticios: las prácticas reales siguen usando las rutas y criterios del catálogo original.

No se ejecutó nuevamente toda la suite Java upstream ni una matriz Windows/Linux x86_64. La comparación histórica de 300/300 XP y su observador SSRF parcial mantiene su propio alcance. Se conserva [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp), [OWASP VulnerableApp](https://owasp.org/projects/vulnerableapp) y el [contexto docente facilitado](https://postgrados.umayor.cl/docentes/ingenieria-seguridad-informacion/), sin afirmar patrocinio institucional.

## Web estática

`tests/verify_site.py` pasó en Chromium dentro de Kali a 390, 768 y 1512 px: imágenes completas, anclas válidas, sin overflow ni errores JS. La publicación incluye solo `site/`.
