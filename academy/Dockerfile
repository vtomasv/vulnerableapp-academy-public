FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATA_DIR=/data \
    KALI_RUNNER_URL=http://kali:9001 \
    OLLAMA_URL=http://ollama:11434 \
    OLLAMA_MODEL=huihui_ai/Qwen3.8-abliterated:27b

WORKDIR /app

COPY academy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --system --uid 1001 --create-home --home-dir /home/academy academy \
    && mkdir -p /data /run/academy-secrets \
    && chown -R 1001:1001 /app /data /run/academy-secrets

COPY academy /app/academy
RUN chown -R 1001:1001 /app/academy

USER 1001:1001
EXPOSE 8000

CMD ["uvicorn", "academy.app:app", "--host", "0.0.0.0", "--port", "8000"]
