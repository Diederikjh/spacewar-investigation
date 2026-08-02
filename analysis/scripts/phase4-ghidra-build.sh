#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

image_name=${SPACEWAR_GHIDRA_IMAGE:-spacewar-ghidra:12.1.2}
build_context='analysis/docker/ghidra'

if ! command -v docker >/dev/null; then
    echo 'Docker is required to build the Phase 4 Ghidra image.' >&2
    exit 1
fi

docker build \
    --pull \
    --tag "$image_name" \
    "$build_context"

image_version=$(docker image inspect \
    --format '{{ index .Config.Labels "org.opencontainers.image.version" }}' \
    "$image_name")
test "$image_version" = '12.1.2'

docker run \
    --rm \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 128 \
    --memory 1g \
    --cpus 1 \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    --entrypoint /bin/sh \
    "$image_name" \
    -c 'java --version && grep "^application.version=" /opt/ghidra/Ghidra/application.properties'
