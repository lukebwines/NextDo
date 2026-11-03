ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-pip
WORKDIR /opt/nextdo
COPY requirements.txt .
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY run.sh /run.sh
RUN chmod +x /run.sh
EXPOSE 8095
CMD ["/run.sh"]
