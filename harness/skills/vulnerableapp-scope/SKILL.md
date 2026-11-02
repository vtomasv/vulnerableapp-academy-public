---
name: vulnerableapp-scope
description: Reconocer los servicios del Compose de VulnerableApp Academy con Nmap y explicar el alcance aislado. Usar al iniciar una sesión de taller o cuando el alumno pida ver las máquinas del laboratorio.
---

# Alcance y reconocimiento

Trabajar exclusivamente dentro del laboratorio autorizado. Usar `lab_discover` para los servicios `target`, `receiver`, `mailpit`, `academy` y `ollama`. No pedir IP, URL, rango, interfaz, gateway ni opciones Nmap libres. No explorar el anfitrión, Internet, otras redes ni otros proyectos Docker.

1. Explicar que las máquinas del taller son contenedores, no máquinas virtuales. El harness no necesita ni tiene acceso al socket Docker.
2. Solicitar aprobación de la llamada. Si el alumno rechaza, no ejecutar otra herramienta para sustituirla.
3. Invocar `lab_discover` con los nombres de servicio. La herramienta resuelve DNS interno y ejecuta Nmap TCP connect, sin privilegios de paquetes crudos.
4. Leer los resultados reales. Distinguir un puerto abierto de un servicio saludable; si el escaneo vence o falla, informar el fallo sin inventar descubrimientos.
5. Explicar IP, nombre, puerto y comando mostrado. Conservar los resultados como evidencia de esta sesión, no como una lista de otros equipos autorizados.

Interpretar `target:9090` como VulnerableApp, `receiver:8081` como receptor inocuo de SSRF/XXE, `mailpit:8025` como buzón de pruebas, `academy:8000` como portal/evaluador y `ollama:11434` como inferencia local. No atacar Academy ni Ollama: solo descubrir su puerto y usar sus funciones docentes autorizadas.

Mostrar un comando real de ejemplo, únicamente para copiar dentro de Kali:

```bash
nmap -sT -n -Pn -sV --version-light -p 9090 target
```

No conceder puntaje por descubrir servicios. Reservar el puntaje a la evidencia que verifique el evaluador independiente.
