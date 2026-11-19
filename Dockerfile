# ChronoLog – production Docker image
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHRONOLOG_HOME=/app

WORKDIR /app

# System deps (none required for pure Python + DuckDB wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.yaml ./
COPY app ./app
COPY templates ./templates
COPY static ./static

# Persist database and secret under /data (mount a volume here)
RUN mkdir -p /data && \
    sed -i 's|db_file: data/chronolog.db|db_file: /data/chronolog.db|' config.yaml

VOLUME ["/data"]
EXPOSE 8080

# Run as non-root
RUN useradd --create-home --shell /bin/bash chronolog \
    && chown -R chronolog:chronolog /app /data
USER chronolog

CMD ["python", "main.py", "-c", "/app/config.yaml"]
