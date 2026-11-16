# The upstream demo is a binary input, not a lower layer of the published image.
# Its source revision and patches are recorded in PROVENANCE.json.
FROM ghcr.io/everest/everest-demo/manager@sha256:9165d0937323ae61ee2e496f68f3c4a465ed9099740e489df1f0161265492756 AS upstream
FROM debian@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc AS extract
# The upstream image contains truncated OS binaries. Reconstruct its OS runtime
# from a dated Debian snapshot instead of copying the local repaired container.
RUN rm /etc/apt/sources.list.d/debian.sources && printf '%s\n' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260201T000000Z bookworm main' \
    'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260201T000000Z bookworm-security main' > /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-yaml python3-cryptography python3-netifaces python3-psutil \
       openssl openjdk-17-jre-headless ca-certificates sqlite3 iproute2 procps coreutils \
       libboost-filesystem1.74.0 libboost-log1.74.0 libboost-program-options1.74.0 libboost-regex1.74.0 libboost-thread1.74.0 \
       libcap2 libevent-2.1-7 libevent-core-2.1-7 libevent-pthreads-2.1-7 libcurl4 libsqlite3-0 libicu72 libyaml-cpp0.7 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir --no-deps -r /requirements.txt
COPY --from=upstream /ext/dist /ext/dist
COPY --from=upstream /ext/source/LICENSE /usr/share/doc/everest-core/LICENSE
COPY sanitize.py /sanitize.py
RUN python3 /sanitize.py

# No original layers, keys, history or machine-specific labels are inherited.
FROM scratch
COPY --from=extract /clean/ /
COPY entrypoint.sh /usr/local/bin/coop-entrypoint
COPY initialize.py /usr/local/bin/coop-initialize.py
ENV PATH=/ext/dist/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/ext/dist/lib \
    PYTHONDONTWRITEBYTECODE=1 \
    MQTT_SERVER_ADDRESS=mqtt-server
LABEL org.opencontainers.image.title="Coop EVerest SIL runtime" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.description="Pinned upstream runtime, stripped of pre-existing PKI and session databases; initialize persistent state on first start"
WORKDIR /state
ENTRYPOINT ["/bin/bash", "/usr/local/bin/coop-entrypoint"]
CMD ["run"]
