#!/usr/bin/env bash

set -euo pipefail

if (( $# != 2 )); then
    printf 'usage: %s RUN_ID {data|cga|trace}\n' "$0" >&2
    exit 2
fi

run_id=$1
label=$2

if [[ ! $run_id =~ ^[a-z0-9][a-z0-9._-]*$ ]]; then
    printf 'error: RUN_ID must use lowercase letters, digits, dots, underscores, or hyphens\n' >&2
    exit 2
fi

case $label in
    data)
        expected_size=$((0x2ab0))
        ;;
    cga)
        expected_size=$((0x4000))
        ;;
    trace)
        expected_size=$((0xc010))
        ;;
    *)
        printf 'error: LABEL must be data, cga, or trace\n' >&2
        exit 2
        ;;
esac

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

source_dump='MEMDUMP.BIN'
target_dir="analysis/dumps/ghost-rendering/$run_id"
target_file="$target_dir/$label.bin"

if [[ ! -f $source_dump ]]; then
    printf 'error: debugger output %s does not exist\n' "$source_dump" >&2
    exit 1
fi

if [[ -e $target_file ]]; then
    printf 'error: refusing to replace %s\n' "$target_file" >&2
    exit 1
fi

actual_size=$(stat -c '%s' -- "$source_dump")
if (( actual_size != expected_size )); then
    printf 'error: %s is %d bytes; expected %d bytes for %s\n' \
        "$source_dump" "$actual_size" "$expected_size" "$label" >&2
    exit 1
fi

mkdir -p -- "$target_dir"
mv -- "$source_dump" "$target_file"
chmod u=rw,go= -- "$target_file"

printf 'Archived debugger dump:\n'
sha256sum -- "$target_file"
