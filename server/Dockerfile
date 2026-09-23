FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
RUN mkdir -p /data && useradd -r -u 1500 api && chown -R api /data /app
USER api

EXPOSE 8080
CMD ["python", "main.py"]
