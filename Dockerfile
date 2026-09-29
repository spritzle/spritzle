# Multi-stage Dockerfile for Spritzle Daemon (spritzled) on Alpine Linux
FROM alpine:latest AS builder

RUN apk add --no-cache \
    python3 \
    py3-build \
    py3-wheel \
    py3-hatchling

WORKDIR /build
COPY pyproject.toml README.md ./
COPY spritzle/ spritzle/
RUN python3 -m build --wheel --no-isolation

# Runtime image
FROM alpine:latest

LABEL org.opencontainers.image.title="Spritzle" \
      org.opencontainers.image.description="Lightweight BitTorrent daemon built around libtorrent with REST API and VPN interface binding" \
      org.opencontainers.image.authors="Andrew Resch <andrewresch@gmail.com>" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

WORKDIR /app

RUN apk add --no-cache \
    ca-certificates \
    curl \
    gosu \
    iproute2 \
    shadow \
    py3-libtorrent-rasterbar \
    py3-aiohttp \
    py3-click \
    py3-installer \
    py3-rich \
    py3-tabulate \
    py3-tomlkit

RUN addgroup -g 1000 spritzle \
    && adduser -u 1000 -G spritzle -h /home/spritzle -D -s /bin/sh spritzle \
    && mkdir -p /config /state /downloads \
    && chown -R spritzle:spritzle /config /state /downloads

COPY --from=builder /build/dist/*.whl /tmp/
RUN python3 -m installer /tmp/*.whl \
    && rm -rf /tmp/*.whl

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

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
