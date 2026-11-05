# Primer reto en Mercado Cordillera

Levanta el laboratorio desde la carpeta del repositorio y abre [Mercado Cordillera](http://localhost:8080/).

```console
docker compose up --build -d --wait
```

Puedes explorar la tienda y los retos antes de crear una cuenta. Usa un alias y una contraseña de práctica en **Mi cuenta** cuando quieras guardar tu progreso. Usa esa misma cuenta en la terminal de Kali.

## Desde el editor de la tienda

1. Pulsa **Empezar primer reto**. Se abre `commandInjection-02`.
2. Revisa la hipótesis y la evidencia esperada. **Cargar control** prepara `ipaddress=127.0.0.1`.
3. Confirma la solicitud y pulsa **Enviar y verificar**. La respuesta del control debe carecer de `VA_LAB_OK`.
4. Pulsa **Cargar ejemplo**. Revisa el valor de `ipaddress`, vuelve a marcar la confirmación y envía la solicitud. El evaluador busca `VA_LAB_OK` en `content` y comprueba el control antes de conceder 100 XP.

Si el editor te lleva al formulario de acceso, crea la cuenta o inicia sesión. **Volver al reto** te devuelve a la ficha.

## A mano en Kali

Pulsa **Kali y harness** en la tienda y abre la terminal del escritorio. Compara las dos respuestas y registra la prueba con tu cuenta.

```bash
lab login
curl -sS --get --data-urlencode 'ipaddress=127.0.0.1' http://target:9090/VulnerableApp/CommandInjection/LEVEL_1
curl -sS --get --data-urlencode 'ipaddress=127.0.0.1|printf VA_LAB_OK' http://target:9090/VulnerableApp/CommandInjection/LEVEL_1
lab request commandInjection-02 --method GET --param 'ipaddress=127.0.0.1|printf VA_LAB_OK'
lab status
```

`curl` muestra la respuesta del servicio. `lab request` pide al evaluador que reproduzca la solicitud y la vincule a tu cuenta. Si ya ganaste los 100 XP desde el editor, repetir la prueba registra el intento y concede 0 XP adicionales. Las prácticas con archivos, sesiones HTTP o pasos de navegador tienen sus propios comandos en **Pasos para practicar a mano en Kali**.

## Con el harness

1. Abre **Harness del taller** en el escritorio de Kali. Si pide un directorio de trabajo, elige `/home/kali`.
2. Pide al agente que invoque `lab_missions` para `commandInjection-02` y explique el control. Revisa la llamada en el panel y pulsa **Allow once** si los argumentos corresponden al reto.
3. Pídele `lab_http` con `ipaddress=127.0.0.1` en un turno. En otro, pide la misma herramienta con `ipaddress=127.0.0.1|printf VA_LAB_OK`. Revisa cada aprobación y compara las respuestas.
4. Cuando hayas revisado la evidencia, pide `lab_submit` con el ejemplo. El helper usa la cuenta que iniciaste con `lab login`. Consulta el resultado en **Mi progreso** y pulsa **Actualizar progreso**.

Para el último paso puedes escribir:

> Ya revisé el control y comprobé VA_LAB_OK en el target local. Invoca lab_submit una sola vez con estos argumentos y espera el panel de aprobación: {"mission_id":"commandInjection-02","request":{"method":"GET","params":{"ipaddress":"127.0.0.1|printf VA_LAB_OK"},"headers":{},"body":null,"content_type":null}}

Usa **Reject** si los argumentos se apartan de la práctica. Ingresa tu contraseña solo en el formulario del taller o en `lab login`. [Guía completa de herramientas](harness/GUIA.md).

## Direcciones y diagnóstico

| Desde | Servicio | Dirección |
|---|---|---|
| Anfitrión | Tienda y entrada a Kali | `http://localhost:8080/` |
| Kali | Tienda | `http://gateway:8080/` |
| Kali | Target para solicitudes de los retos | `http://target:9090/VulnerableApp/` |
| Kali | Harness | `http://127.0.0.1:2323/` |
| Tienda | Correo ficticio | **Correo de práctica** en el pie de página |

Si falla el arranque, revisa `docker compose ps` y los logs del servicio afectado. `init` y `model-init` son tareas de una sola ejecución y terminan con código 0 cuando completan su trabajo. [Diagnóstico de arranque](INICIO.md).
