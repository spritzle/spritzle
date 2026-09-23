# Multi-stage Dockerfile for Spritzle Daemon (spritzled)
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY spritzle/ spritzle/

RUN pip install --no-cache-dir --upgrade pip build wheel \
    && python -m build --wheel

# Runtime image
FROM python:3.13-slim

LABEL org.opencontainers.image.title="Spritzle" \
      org.opencontainers.image.description="Lightweight BitTorrent daemon built around libtorrent with REST API and VPN interface binding" \
      org.opencontainers.image.authors="Andrew Resch <andrewresch@gmail.com>" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gosu \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Create spritzle non-root user and directories
RUN groupadd -g 1000 spritzle \
    && useradd -u 1000 -g spritzle -d /home/spritzle -m -s /bin/bash spritzle \
    && mkdir -p /config /state /downloads \
    && chown -R spritzle:spritzle /config /state /downloads

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl[daemon] \
    && rm -rf /tmp/*.whl

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment defaults
ENV SPRITZLE_CONFIG_DIR=/config \
    SPRITZLE_STATE_DIR=/state \
    SPRITZLE_SAVE_PATH=/downloads \
    PYTHONUNBUFFERED=1

EXPOSE 17382 6881 6881/udp

VOLUME ["/config", "/state", "/downloads"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:17382/status || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["spritzled", "-H", "0.0.0.0", "-p", "17382", "-c", "/config", "-s", "/state"]
