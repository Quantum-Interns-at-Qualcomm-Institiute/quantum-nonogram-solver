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

EXPOSE 5055

CMD ["python", "tools/webapp.py"]
