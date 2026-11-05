#!/bin/sh
set -eu

: "${OLLAMA_MODEL:=qwen3:4b}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

log_file=/tmp/ollama-model-init.log
ollama serve >"$log_file" 2>&1 &
ollama_pid=$!
cleanup() {
    kill "$ollama_pid" 2>/dev/null || true
    wait "$ollama_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
i=0
while [ "$i" -lt 120 ]; do
    if ollama list >/dev/null 2>&1; then
        ready=1
        break
    fi
    i=$((i + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "ollama daemon did not become ready" >&2
    cat "$log_file" >&2 || true
    exit 1
fi

# The only network bootstrap action is this explicit model pull.
if ollama show "$OLLAMA_MODEL" >/dev/null 2>&1; then
    echo "Modelo disponible en el volumen local; no se necesita descargar."
else
    ollama pull "$OLLAMA_MODEL"
fi
