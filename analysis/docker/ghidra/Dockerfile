# syntax=docker/dockerfile:1

FROM eclipse-temurin:21.0.11_10-jdk-jammy@sha256:9d8dcf999b0bce2453e913823595a5ff2a4e8e9e5d5241b45280d0ff069818ec AS extract

ARG GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.2_build/ghidra_12.1.2_PUBLIC_20260605.zip
ARG GHIDRA_SHA256=b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d

WORKDIR /tmp/ghidra-build

RUN set -eux; \
    wget --progress=dot:giga --output-document=ghidra.zip "$GHIDRA_URL"; \
    echo "$GHIDRA_SHA256  ghidra.zip" | sha256sum --check --strict; \
    jar --extract --file ghidra.zip; \
    mv ghidra_12.1.2_PUBLIC /opt/ghidra

FROM eclipse-temurin:21.0.11_10-jdk-jammy@sha256:9d8dcf999b0bce2453e913823595a5ff2a4e8e9e5d5241b45280d0ff069818ec

LABEL org.opencontainers.image.title="Spacewar1985 Ghidra investigation environment" \
      org.opencontainers.image.version="12.1.2" \
      org.opencontainers.image.source="https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.2_build"

COPY --from=extract /opt/ghidra /opt/ghidra

# The JDK ZIP extractor does not restore Unix permission bits. Restore execute
# permission deterministically for scripts and native ELF programs only.
RUN set -eux; \
    find /opt/ghidra -type f -exec sh -c '\
        for file do \
            magic=$(od -An -N4 -tx1 "$file" | tr -d " \\n"); \
            case "$magic" in \
                2321*|7f454c46) chmod 0755 "$file" ;; \
            esac; \
        done \
    ' sh {} +

WORKDIR /work

CMD ["/opt/ghidra/support/analyzeHeadless"]
