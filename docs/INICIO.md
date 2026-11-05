# Instalar y diagnosticar el taller

Instala Docker con Compose v2 y usa contenedores Linux. Descarga el repositorio completo, abre una terminal en su carpeta y ejecuta:

```console
docker compose up --build -d --wait
```

Abre [Mercado Cordillera](http://localhost:8080/) y sigue [el primer reto](COMENZAR.md). El primer arranque necesita conexión para descargar imágenes, dependencias y pesos. Las prácticas y la inferencia se ejecutan dentro de Docker.

## Diagnóstico

```console
docker compose config --quiet
docker compose ps -a
docker compose logs --tail=80 model-init ollama gateway academy kali target
```

- Si el puerto está ocupado, añade `LAB_PORT=8082` a `.env` y entra por `http://localhost:8082/`.
- Si falla la descarga del modelo, revisa el log de `model-init` y repite el comando de arranque cuando se recupere la conexión.
- Si noVNC muestra una desconexión, abre **Kali y harness** de nuevo cuando `kali` y `gateway` estén saludables.
- Si el modelo tarda demasiado en responder, revisa el estado de `ollama` y los recursos de la VM de Docker. `.env.example` contiene los parámetros de CPU, memoria e inferencia.

Para levantar la tienda y practicar manualmente mientras resuelves un fallo de descarga, ejecuta:

```console
docker compose up --build -d --wait gateway gateway-netlock
```

## Conservar el progreso

```console
docker compose stop
docker compose up -d --wait
```

Los volúmenes conservan cuentas y XP, el escritorio de Kali y los pesos. Usa el mismo nombre de proyecto al actualizar. Cada alumno debe usar una instancia propia para que los cambios en el target y los archivos de Kali queden separados.
