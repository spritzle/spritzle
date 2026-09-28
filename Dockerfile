# Multi-stage Dockerfile for Spritzle Daemon (spritzled) on Arch Linux
FROM archlinux:base AS builder

RUN pacman -Syu --noconfirm && \
    pacman -S --noconfirm --needed \
        python \
        python-build \
        python-wheel \
        python-hatchling

WORKDIR /build

COPY pyproject.toml README.md ./
COPY spritzle/ spritzle/

RUN python -m build --wheel --no-isolation

# Preparation stage: install packages, strip bloat
FROM archlinux:base AS runtime-rootfs

WORKDIR /app

# 1. Prevent pacman from extracting doc, man, and locale files
# 2. Install runtime dependencies and official libtorrent-rasterbar (with python bindings)
# 3. Strip locale-archive, docs, translations, pacman cache, and python caches in a single layer
RUN sed -i '/NoExtract/d' /etc/pacman.conf && \
    echo 'NoExtract = usr/share/help/* usr/share/doc/* usr/share/man/* usr/share/locale/* usr/share/info/* usr/share/gir-1.0/* usr/share/hwdata/*' >> /etc/pacman.conf && \
    pacman -Syu --noconfirm && \
    pacman -S --noconfirm --needed \
        ca-certificates \
        curl \
        iproute2 \
        libtorrent-rasterbar \
        python \
        python-aiohttp \
        python-click \
        python-installer \
        python-rich \
        python-tabulate \
        python-tomlkit && \
    # Rebuild minimal locale-archive (saves ~120MB)
    rm -rf /usr/lib/locale/* && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen && \
    # Purge docs, man pages, locales, hardware databases, pacman DBs and keys
    rm -rf /usr/share/man /usr/share/doc /usr/share/locale /usr/share/info \
           /usr/share/hwdata /usr/share/gir-1.0 /usr/share/i18n /usr/share/file /usr/share/kbd \
           /usr/share/iana-etc /usr/share/pacman /usr/share/gettext /usr/share/makepkg \
           /usr/share/bash-completion /usr/share/dbus-1 /usr/share/zoneinfo/right \
           /etc/pacman.d /etc/pacman.conf /var/lib/pacman /var/cache/pacman /var/log/pacman.log && \
    # Prune non-essential terminfo (keep only xterm, screen, linux, vt100)
    find /usr/share/terminfo -type f ! -name "xterm*" ! -name "screen*" ! -name "linux*" ! -name "vt100*" ! -name "ansi*" -delete 2>/dev/null || true && \
    find /usr/share/terminfo -type d -empty -delete 2>/dev/null || true && \
    # Clean systemd/udev non-container services
    rm -rf /usr/lib/systemd /usr/lib/udev /usr/lib/pkcs11 && \
    # Clean developer binaries, linkers, GPG, systemd tools, and debug utilities (saves ~65MB)
    rm -f /usr/bin/xgettext /usr/bin/gettext* /usr/bin/msg* \
          /usr/bin/ld* /usr/bin/as /usr/bin/readelf /usr/bin/objdump /usr/bin/dwp /usr/bin/gprofng* /usr/bin/nm /usr/bin/size /usr/bin/strings \
          /usr/bin/sqlite3_* /usr/bin/sqldiff /usr/bin/showstat4 /usr/bin/showdb /usr/bin/dbhash /usr/bin/dbdump \
          /usr/bin/captree /usr/bin/index_usage /usr/bin/pcre2test /usr/bin/localedef /usr/bin/sln \
          /usr/bin/systemd-* /usr/bin/systemctl /usr/bin/udevadm \
          /usr/bin/gpg* /usr/bin/dirmngr /usr/bin/pinentry* \
          /usr/bin/cryptsetup /usr/bin/fsck* /usr/bin/mkfs* /usr/bin/e2fsck /usr/bin/tune2fs /usr/bin/badblocks && \
    # Clean unused sanitizers, fortran, and profiler libraries (saves ~20MB)
    rm -f /usr/lib/libgfortran* /usr/lib/libasan* /usr/lib/libtsan* /usr/lib/liblsan* /usr/lib/libubsan* /usr/lib/libgprofng* /usr/lib/libbfd* && \
    rm -rf /usr/lib/ldscripts /usr/lib/gprofng /usr/lib/gnupg && \
    # Prune non-UTF-8 gconv encodings
    find /usr/lib/gconv -type f ! -name "UTF*" ! -name "gconv-modules*" ! -name "ISO8859-1*" -delete 2>/dev/null || true && \
    # Clean python bytecache, test suites, and unused stdlib modules (saves ~55MB)
    rm -rf /usr/lib/python*/ensurepip \
           /usr/lib/python*/idlelib \
           /usr/lib/python*/test \
           /usr/lib/python*/turtledemo \
           /usr/lib/python*/tkinter \
           /usr/lib/python*/pydoc_data \
           /usr/lib/python*/unittest \
           /usr/lib/python*/_pyrepl \
           /usr/lib/python*/config-3* \
           /usr/include \
           /usr/share/licenses && \
    find /usr/lib/python* -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/lib/python* -name "*.pyc" -delete 2>/dev/null || true && \
    find /usr/lib/python* -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/lib -name "*.a" -delete 2>/dev/null || true

# Install gosu for root privilege-dropping
ARG GOSU_VERSION=1.17
RUN ARCH="$(uname -m)"; \
    case "$ARCH" in \
        x86_64) GOSU_ARCH="amd64" ;; \
        aarch64) GOSU_ARCH="arm64" ;; \
        *) GOSU_ARCH="$ARCH" ;; \
    esac; \
    curl -sSL -o /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/${GOSU_VERSION}/gosu-${GOSU_ARCH}" && \
    chmod +x /usr/local/bin/gosu

# Create spritzle non-root user and directories
RUN groupadd -g 1000 spritzle \
    && useradd -u 1000 -g spritzle -d /home/spritzle -m -s /bin/bash spritzle \
    && mkdir -p /config /state /downloads \
    && chown -R spritzle:spritzle /config /state /downloads

# Install the built spritzle wheel into system site-packages
COPY --from=builder /build/dist/*.whl /tmp/
RUN python -m installer /tmp/*.whl \
    && rm -rf /tmp/*.whl

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Final flattened runtime image
FROM scratch

LABEL org.opencontainers.image.title="Spritzle" \
      org.opencontainers.image.description="Lightweight BitTorrent daemon built around libtorrent with REST API and VPN interface binding" \
      org.opencontainers.image.authors="Andrew Resch <andrewresch@gmail.com>" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

COPY --from=runtime-rootfs / /

WORKDIR /app

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
