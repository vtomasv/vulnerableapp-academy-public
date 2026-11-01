# Guía para el instructor

## Preparar el aula

Cada alumno inicia su propio Compose en su equipo. No conviertas el laboratorio en un servidor central público: el escritorio, las semillas H2 y algunos estados de caché son compartidos dentro de una instancia. Las cuentas separan puntaje, no recursos de target o ventanas de Kali.

Antes de la clase, pide que completen el primer build y la descarga del modelo. Comprueba `docker compose ps` y los logs de `model-init`; que el portal esté abierto no prueba que Qwen ya terminó de descargar. El taller estático y el puntaje no dependen de la IA. En equipos con memoria limitada usa una variante Qwen menor y verifica calidad/latencia antes del curso; no existe un tamaño mínimo medido universal.

No solicites contraseñas reales ni datos personales. Explica que «VulnerableApp» y «Academy» tienen cuentas distintas. Revisa las reglas de alcance: target, receiver y Mailpit son los únicos objetivos de las prácticas; la red del anfitrión e Internet quedan fuera.

## Orden pedagógico recomendado

Comienza con HTTP y `curl`: distinguir URL, query, headers, cuerpo, código de estado y representación JSON. Usa `curl -i` antes de cualquier vulnerabilidad. Pide que el alumno prediga el resultado y señale qué parte de la entrada controla.

Continúa con controles simples: redirecciones, cabeceras de framing, path traversal y comandos con el marcador `VA_LAB_OK`. Contrasta inmediatamente con el nivel corregido. El objetivo no es memorizar un payload, sino identificar por qué se interpreta la entrada y qué cambio evita ese comportamiento.

Introduce SQL y LDAP después de entender la sintaxis de la consulta. No confundir una consulta vacía, un error ni un HTTP 200 con un acceso exitoso. Luego autenticación, JWT, IDOR, sesiones, OTP y recuperación de contraseña: estos flujos requieren mantener cookies y comparar identidades o estados. Los ejercicios manuales no deben presentarse como automáticamente superados.

Trata XSS, SSRF, XXE, deserialización y carga de archivos al final de la primera vuelta. Los marcadores son inocuos: no se roban cookies ni se apuntan llamadas a sistemas externos. En XSS, separa almacenamiento, reflexión y ejecución. En SSRF, el receptor local permite observar que el servidor hizo una solicitud. En XXE, usa expansión acotada; no emplees cargas de denegación de servicio.

Cierra con criptografía y caché. Para criptografía, primero pide al alumno resolver por su cuenta. `lab-crypto 2` muestra una solución guiada de Base64 y el comando de registro; `lab-crypto 5` compara únicamente las diez semillas públicas del commit y calcula hashes localmente. `--submit` envía explícitamente el resultado con la sesión del alumno; sin esa opción no registra puntos. No se envían hashes a páginas públicas. El nivel 1 requiere inspeccionar la base de entrenamiento como indica la guía; el nivel 11 es análisis del control BCrypt, no una invitación a una búsqueda ilimitada.

## Método para cada práctica

1. El alumno describe la entrada y predice el comportamiento.
2. Ejecuta un control benigno contra el servicio local.
3. Ejecuta una sola modificación y conserva la respuesta.
4. Explica qué evidencia demuestra y qué **no** demuestra.
5. Registra un intento con `lab request`, o entrega revisión manual si el catálogo indica 0 XP.
6. Compara la mitigación y el nivel seguro antes de continuar.

El puntaje funciona como feedback, no como examen anti-trampas. Los criterios, comandos y soluciones son visibles. No premies el número de alertas de ZAP, el lanzamiento de sqlmap ni la cantidad de solicitudes. Premia la explicación y la comparación con controles durante la discusión.

## Tutor Qwen

Pide preguntas concretas: «Mi respuesta contiene X pero el control también: ¿qué falta para concluir?» o «Explica la diferencia entre reflejar texto y ejecutar un marcador DOM». Las propuestas de herramientas requieren aprobación visible. El tutor no ejecuta shell libre, no elige un destino y no concede puntos. Sus llamadas de herramientas se presentan como evidencia no confiable; el alumno vuelve a contrastarlas con la guía y el código.

El modelo Qwen3 ablacionado es experimental y puede producir contenido incorrecto o inapropiado; está pensado para un aula adulta, controlada y con revisión. Sustituye el modelo por Qwen oficial si no es adecuado para la audiencia. No confundas la reducción de filtros con una garantía de neutralidad, calidad o ausencia de rechazos.

## Restablecer una práctica

Usa `docker compose up -d --force-recreate target target-netlock` para recrear las semillas del target y su firewall asociado. Avisa antes: se pierden sesiones, tokens y cambios de estado del target, pero no los puntos de Academy. No borres volúmenes para una pausa ni reinicies otro alumno sin coordinarlo.

Para conservar la evidencia, descarga la exportación JSON del portal. Es un registro de progreso, no una copia restaurable integral. Una copia de recuperación del laboratorio requiere respaldar también los volúmenes, con los servicios detenidos y conforme a las políticas del aula.
