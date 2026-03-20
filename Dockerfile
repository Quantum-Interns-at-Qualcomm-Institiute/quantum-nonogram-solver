FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY nonogram/ nonogram/
COPY tools/ tools/

RUN pip install --no-cache-dir "."

EXPOSE 5055

CMD ["python", "tools/webapp.py"]
