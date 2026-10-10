FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
