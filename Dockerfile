FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY requirements/py3.12.lock ./requirements/
COPY nonogram/ nonogram/
COPY tools/ tools/

# The lock fixes the exact dependency set, so two builds of one commit are the same
# image. It is resolved for this base image's Python; regenerate with `make lock`.
RUN pip install --no-cache-dir -r requirements/py3.12.lock \
    && pip install --no-cache-dir --no-deps .

# Drop privileges: nothing here needs root at runtime.
RUN useradd --create-home --uid 10001 nonogram && chown -R nonogram:nonogram /app
USER nonogram

# Production WSGI server (gunicorn) instead of the Werkzeug dev server. ONE
# gthread worker: server state (busy/hw_config) is per-process, and
# Flask-SocketIO's threading mode under gunicorn serves Socket.IO via
# long-polling (no WebSocket) — the client falls back transparently. TLS is
# the platform edge's job here.
CMD ["sh", "-c", "exec gunicorn --worker-class gthread --workers 1 --threads 16 --timeout 120 --bind 0.0.0.0:${PORT:-8080} tools.webapp:app"]
