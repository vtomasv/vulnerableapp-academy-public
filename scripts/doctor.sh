#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
    echo 'Docker CLI no está instalado o no está en PATH.' >&2
    exit 2
fi

echo '== docker compose config =='
docker compose config --quiet

echo '== service status =='
docker compose ps

echo '== Kali lab doctor =='
if docker compose ps --services --filter status=running | grep -qx kali; then
    docker compose exec -T kali lab doctor
else
    echo 'Kali no está ejecutándose; inicia el laboratorio con: docker compose up -d --build' >&2
    exit 1
fi
