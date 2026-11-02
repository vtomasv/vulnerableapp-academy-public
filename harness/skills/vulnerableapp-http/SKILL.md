---
name: vulnerableapp-http
description: Guiar ejercicios HTTP de VulnerableApp con parámetros, cabeceras, cuerpos y comparación de controles. Usar para practicar inyección SQL, autenticación, XSS, traversal, SSRF, XXE o redirecciones en misiones del catálogo local.
---

# Práctica HTTP guiada

Tomar el identificador y la receta de la misión del portal o de `/opt/vulnerableapp-academy/docs/TALLER.md`. Mantener el nivel elegido. No cambiar de objetivo ni inventar rutas. `lab_http` fija la URL al `target` y a la ruta del catálogo; no admite destinos arbitrarios.

1. Explicar el propósito del parámetro y formular una hipótesis. Pedir al alumno que prediga qué respuesta indicaría una vulnerabilidad.
2. Preparar una solicitud de control inocua. Mostrar método, parámetros, cabeceras y cuerpo, y pedir aprobación antes de usar `lab_http`.
3. Leer la respuesta real. Explicar estado HTTP, cabeceras y cuerpo sin confundir un `200` con éxito del objetivo.
4. Cambiar una sola variable. Para SQLi, comparar una entrada normal con el payload de la receta local; para XSS, usar el marcador inofensivo del taller. No extraer datos ajenos al laboratorio.
5. Pedir una nueva aprobación para el nuevo intento. No ejecutar en bucle ni continuar automáticamente tras una negativa.
6. Comparar ambas respuestas y explicar la diferencia. Si solo hay reflexión XSS, no afirmar ejecución JavaScript. Si hay `Location`, no seguir la redirección fuera del target.
7. Pedir al alumno que explique una mitigación y que prepare el intento verificable con `lab_submit`.

Usar objetos `request` con `method`, `params`, `headers`, `body` y `content_type`. Los parámetros son texto; representar valores especiales como cadenas JSON, no como instrucciones de shell. No duplicar parámetros entre formulario y query. No insertar saltos de línea en cabeceras. Respetar el límite de cuerpo de 16 KiB.

Mostrar el comando real que devuelve la herramienta. Todas las herramientas y comandos se ejecutan dentro de Kali. No instalar paquetes durante el taller, habilitar proveedores externos ni intentar modificar las políticas del harness.
