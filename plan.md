# VulnerableApp Academy

El entregable es un repositorio autónomo y portable, para ejecutar localmente con Docker Compose, no un sitio público. Se incluye el código Java original fijado al commit 4df80bbcd42682ecf26334f12c568e0f4a326c1a, con atribución y licencia originales. Los cambios viven fuera de vendor salvo ajustes de empaquetado documentados.

## Arquitectura

Un gateway nginx publica únicamente 127.0.0.1:8080. El portal Python/FastAPI sirve una interfaz en español, usuarios individuales, SQLite persistente, misiones, evidencias y tutor Qwen. Kali contiene XFCE, Firefox, terminal, noVNC, curl, jq, Python, herramientas HTTP y un runner de herramientas tipadas. No se montan directorios del anfitrión, dispositivos ni el socket Docker. Los servicios vulnerables, el receptor y el correo viven en redes internas. La descarga inicial de Qwen usa un servicio temporal que termina antes del arranque offline de Ollama.

La detección de objetivos usa solicitudes que atraviesan un proxy de evidencias autenticado, ligado al usuario y misión. El proxy observa la respuesta real, contrasta criterios definidos por misión y escribe puntos una sola vez mediante transacción. No se otorga puntuación por pulsar un botón ni por una afirmación del modelo. Las demostraciones que requieren navegador se separan de la evidencia HTTP y se explican sus límites. Los niveles completos del original se listan como exploración; solo tienen puntaje las misiones con verificador implementado.

El tutor puede proponer y ejecutar, tras aprobación explícita del alumno, solo herramientas con parámetros estructurados y destino fijo. No tiene shell arbitrario. El runner reside dentro de Kali, con usuario distinto al escritorio y API privada autenticada; el modelo no tiene acceso a credenciales, puntuación ni cuentas. La guía manual permite practicar en la aplicación original.

## Estructura

`vendor/` contiene el original; `academy/` backend, frontend y catálogo; `kali/` imagen y harness; `gateway/` proxy; `docs/` tutorial y arquitectura; `tests/` pruebas; `scripts/` diagnóstico y generación de catálogo. `research/` conserva las guías por familia derivadas del código original.

## Diseño

Interfaz tipo videojuego técnico: estética de consola de misión, fondo carbón, color ámbar para acciones y turquesa para objetivos logrados. Navegación lateral por capítulos, panel central de briefing y terminal con comandos copiable, progreso y experiencia siempre visibles. Tipografía del sistema para lectura y monoespaciada para comandos; sin recursos externos ni fuentes descargadas. El portal no necesita ilustraciones decorativas. Marca: VA / ACADEMY con retícula de identificación; voz didáctica: «Observa la respuesta antes de avanzar» y «Objetivo verificado con evidencia del laboratorio». Animaciones discretas, respetando reduced-motion.

## Límites

Docker comparte kernel con el anfitrión: aislamiento reduce riesgo, no equivale a una VM ni protege ante un escape de contenedor. Compatible por diseño con Linux amd64/arm64 y Docker Desktop Windows/macOS; se documentará lo probado realmente. CPU por defecto para portabilidad; GPU NVIDIA opcional. Qwen estándar local con soporte tools, sin promesa de un modelo sin restricciones. No incluir agentes de explotación externos ni publicar el laboratorio.
