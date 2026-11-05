# Mercado Cordillera · VulnerableApp Academy

Tienda chilena simulada para el taller universitario de seguridad web. El laboratorio reúne 189 retos en 20 familias, un editor para practicar desde la tienda y un escritorio Kali con terminal, navegador y pentest-harness. Todo se ejecuta con Docker Compose.

## Arrancar el laboratorio

Necesitas Docker con Compose v2 y un navegador. El primer arranque descarga las imágenes, dependencias y unos 2,5 GB de pesos del modelo local. [Qwen3 4B en Ollama](https://ollama.com/library/qwen3:4b).

```console
git clone https://github.com/vtomasv/vulnerableapp-academy-public.git
cd vulnerableapp-academy-public
docker compose up --build -d --wait
```

Abre **http://localhost:8080**. La portada es Mercado Cordillera. Pulsa **Empezar primer reto** para abrir `commandInjection-02` o busca otra misión en **Retos del taller**.

## Practicar y registrar evidencia

- **Desde la tienda.** En el primer reto, marca la confirmación y envía el control. Carga el ejemplo, revisa el parámetro y vuelve a enviarlo. El editor pide una cuenta del taller en el primer envío. La evidencia del ejemplo debe incluir `VA_LAB_OK`.
- **A mano en Kali.** Pulsa **Kali y harness**. Abre una terminal y sigue **Pasos para practicar a mano en Kali** en la ficha. Usa `lab login` con la misma cuenta y `lab request` para registrar un intento puntuable.
- **Con el harness.** En el escritorio de Kali, abre **Harness del taller**. Pide una llamada por turno y revisa sus argumentos antes de pulsar **Allow once**. `lab_submit` registra la evidencia usando la sesión de `lab login`.

Los retos con verificación automática otorgan XP una vez por cuenta. Los retos guiados se revisan con los pasos y la evidencia que indica la ficha. **Mi progreso** muestra el total, con un botón para actualizarlo después de practicar desde Kali.

[Primer reto paso a paso](docs/COMENZAR.md) · [Guía de harness](docs/harness/GUIA.md) · [Tutorial por familias](docs/TALLER.md)

## Estado y datos

```console
docker compose ps
docker compose logs --tail=80 model-init ollama gateway academy kali target
docker compose stop
```

Para una clase simultánea, usa una instancia Compose por alumno. Cada instancia conserva cuentas, progreso y pesos del modelo en volúmenes. Para actualizar una instalación, mantén el mismo nombre de proyecto Compose y vuelve a ejecutar el comando de arranque. `docker compose down -v` borra esos volúmenes.

El gateway publica `127.0.0.1:8080`. Si el puerto está ocupado, define `LAB_PORT` en `.env` y abre la tienda en ese puerto. Kali, el target vulnerable, el harness y Ollama usan la red interna. Usa datos ficticios en el laboratorio local.

El modelo de aula se configura con `OLLAMA_MODEL`. Puedes revisar el modelo activo con `docker compose exec ollama ollama list`. [Configuración histórica del modelo de 27B](docs/MAC_27B.md).

## Repetir las pruebas

```console
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/cordillera_ui_e2e.py
docker compose exec -T --user kali kali python3 /opt/vulnerableapp-academy/tests/cordillera_harness_e2e.py
```

Las pruebas de integración usan cuentas ficticias. Ejecuta una prueba de harness a la vez porque comparte la sesión de `lab login` de Kali.

## Créditos

Adaptación docente independiente basada en [SasanLabs/VulnerableApp](https://github.com/SasanLabs/VulnerableApp) y [S1N6H/pentest-harness](https://github.com/S1N6H/pentest-harness). La [página pública del proyecto](https://vtomasv.github.io/vulnerableapp-academy-public/) conserva las capturas y resultados de versiones anteriores. [Atribuciones](docs/ATRIBUCION.md).
