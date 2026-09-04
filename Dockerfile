FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY nonogram/ nonogram/
COPY tools/ tools/

RUN pip install --no-cache-dir "."

# Generate self-signed dev certs so the server starts in HTTPS mode
RUN mkdir -p .certs && \
    openssl req -x509 -newkey rsa:2048 \
      -keyout .certs/key.pem -out .certs/cert.pem \
      -days 365 -nodes \
      -subj "/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

ENV DEV_CERT_DIR=/app/.certs

# Production WSGI server (gunicorn) instead of the Werkzeug dev server. ONE
# gthread worker: server state (grid/busy/hw_config) is per-process, and
# Flask-SocketIO's threading mode under gunicorn serves Socket.IO via
# long-polling (no WebSocket) — the client falls back transparently. TLS is
# the platform edge's job here (the dev certs remain for direct local runs).
CMD ["sh", "-c", "exec gunicorn --worker-class gthread --workers 1 --threads 16 --timeout 120 --bind 0.0.0.0:${PORT:-8080} tools.webapp:app"]
