ARG BUILD_FROM=ghcr.io/home-assistant/base:latest
FROM $BUILD_FROM

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY requirements.txt /tmp/requirements.txt

RUN apk add --no-cache \
    python3 \
    py3-pip \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm -rf /tmp/requirements.txt /root/.cache

ENV PATH=/opt/venv/bin:$PATH

COPY server.py /app/server.py
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
