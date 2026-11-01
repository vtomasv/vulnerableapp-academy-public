FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RECEIVER_BIND=0.0.0.0 \
    RECEIVER_PORT=8081 \
    RECEIVER_DATA=/data/requests.jsonl

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin receiver \
    && mkdir -p /app /data \
    && chown -R receiver:receiver /app /data

COPY app.py /app/app.py
RUN chmod 0755 /app/app.py && chown receiver:receiver /app/app.py

USER receiver
WORKDIR /app
EXPOSE 8081
HEALTHCHECK --interval=15s --timeout=5s --retries=12 CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=3).read()"
ENTRYPOINT ["python3", "/app/app.py"]
