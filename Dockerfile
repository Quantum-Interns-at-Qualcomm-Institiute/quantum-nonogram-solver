FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY tools/ tools/
COPY nonogram/ nonogram/

RUN pip install --no-cache-dir ".[web]"

CMD ["python", "tools/webapp.py"]
