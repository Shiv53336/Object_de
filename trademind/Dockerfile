FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRADEMIND_CONFIG_DIR=/app/config \
    TRADEMIND_DATA_DIR=/app/data

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && useradd --create-home --uid 1000 trademind && mkdir -p /app/data \
    && chown trademind:trademind /app/data
COPY config ./config

USER trademind
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["trademind", "api", "--host", "0.0.0.0", "--port", "8000"]
