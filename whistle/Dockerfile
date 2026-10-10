FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    NEEDLE_TELEMETRY=0 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && rm -rf /root/.cache
COPY server.py run.sh ./
CMD ["./run.sh"]
