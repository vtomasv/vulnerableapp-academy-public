---
name: vulnerableapp-evidence
description: Enviar y explicar evidencia verificable y puntaje individual de VulnerableApp Academy sin inventar éxitos. Usar cuando el alumno considere resuelta una misión, quiera registrar progreso o necesite interpretar un intento fallido.
---

# Evidencia y progreso individual

No calcular ni escribir puntajes desde el modelo. Usar `lab_submit` para enviar el identificador y la solicitud del alumno al evaluador separado. La API reproduce el intento con el runner de Kali y decide si la evidencia cumple el objetivo. Usar `lab_progress` después para leer el estado de la sesión; no leer SQLite, tokens ni credenciales.

1. Pedir al alumno que inicie su cuenta en una terminal de Kali con `lab login`. No pedir la contraseña ni el token en el chat. Si comparte escritorio, indicar `lab logout` al terminar.
2. Consultar `lab_missions` con el ID exacto y explicar su criterio. Mostrar la solicitud completa que se enviará, con método, parámetros, cabeceras, cuerpo y `content_type`; ocultar cualquier credencial personal.
3. Verificar que ya hubo control y payload permitido con `lab_http` cuando la misión lo requiera. No sustituir la evidencia real por una predicción.
4. Pedir aprobación explícita de `lab_submit`. Un permiso anterior de exploración o de control no autoriza el envío de otro intento; una negativa detiene el flujo.
5. Leer `success`, `awarded`, `score`, `evidence_summary` y `server` devueltos por Academy. Si no hay respuesta, si el evaluador falla o si `success` es falso, informar que no se ha demostrado el objetivo.
6. Usar `lab_progress` con una aprobación propia para comparar el score/máximo y los eventos que Academy reporte. Distinguir XP concedido en este intento de XP total. Repetir una misión lograda no debe duplicar sus puntos; no ejecutar repeticiones para farmear XP.
7. Explicar el resultado con evidencia concreta. No sustituir un resultado del navegador por una coincidencia textual ni afirmar explotación por un código HTTP aislado.
8. Proponer el siguiente paso o una mitigación; no ejecutarlo sin otra aprobación.

Para comprobar y exportar el progreso desde la terminal:

```bash
lab status
lab export
lab logout
```

No leer SQLite, montar volúmenes del evaluador, acceder a la clave del runner ni llamar rutas administrativas. No prometer aislamiento entre personas que usan simultáneamente el mismo escritorio Kali: recomendar una instancia Compose por alumno o turnos con cierre de sesión. El progreso del portal es individual por cuenta; la terminal usa la cuenta iniciada en `lab login`. No dar estimaciones de tiempo de resolución.
