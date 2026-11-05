FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY permitpass ./permitpass
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "permitpass.main:app", "--host", "0.0.0.0", "--port", "8000"]
