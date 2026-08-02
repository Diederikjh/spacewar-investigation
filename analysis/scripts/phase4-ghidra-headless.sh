#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

image_name=${SPACEWAR_GHIDRA_IMAGE:-spacewar-ghidra:12.1.2}
source_binary='analysis/work/Spacewar1985.exe'
function_ledger='analysis/function-ledger.csv'
script_store='analysis/ghidra-scripts'
ghidra_dir='analysis/ghidra'
project_store="$ghidra_dir/projects"
home_store="$ghidra_dir/home"
export_store="$ghidra_dir/exports"

if (( $# == 0 )); then
    echo "usage: $0 <analyzeHeadless arguments...>" >&2
    exit 2
fi

test -f "$source_binary"
test -f "$function_ledger"
test -d "$script_store"
if ! command -v docker >/dev/null; then
    echo 'Docker is required to run the Phase 4 Ghidra image.' >&2
    exit 1
fi
mkdir -p "$project_store" "$home_store" "$export_store"

run_uid=$(id -u)
run_gid=$(id -g)

exec docker run \
    --rm \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 512 \
    --memory 4g \
    --cpus 2 \
    --tmpfs /tmp:rw,nosuid,nodev,size=256m \
    --user "$run_uid:$run_gid" \
    --env HOME=/work/home \
    --mount "type=bind,src=$project_dir/$source_binary,dst=/input/Spacewar1985.exe,readonly" \
    --mount "type=bind,src=$project_dir/$function_ledger,dst=/input/function-ledger.csv,readonly" \
    --mount "type=bind,src=$project_dir/$script_store,dst=/scripts,readonly" \
    --mount "type=bind,src=$project_dir/$project_store,dst=/projects" \
    --mount "type=bind,src=$project_dir/$home_store,dst=/work/home" \
    --mount "type=bind,src=$project_dir/$export_store,dst=/exports" \
    --entrypoint /opt/ghidra/support/analyzeHeadless \
    "$image_name" \
    "$@"
