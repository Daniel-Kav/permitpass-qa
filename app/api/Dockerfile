FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY permitpass ./permitpass
# Capacity defaults (#36); override per environment. Postgres connections used = WEB_CONCURRENCY x (pool + overflow)
ENV WEB_CONCURRENCY=4 \
    INIT_DB_ON_STARTUP=false \
    MAX_IN_FLIGHT=32 \
    DB_POOL_SIZE=10 \
    DB_MAX_OVERFLOW=10
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
# Pre-start once (tables, demo seed), then N workers that don't race on start-up
CMD ["sh", "-c", "python -m permitpass.prestart && exec uvicorn permitpass.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY}"]
