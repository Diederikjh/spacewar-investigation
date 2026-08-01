#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

source_binary='analysis/work/Spacewar1985.exe'
run_dir='analysis/work/dosbox-run'
trace_dir='analysis/traces/phase3'
run_binary="$run_dir/SPACEWAR.EXE"

test -f "$source_binary"
command -v dosbox-x >/dev/null

mkdir -p "$run_dir" "$trace_dir"
cp -- "$source_binary" "$run_binary"
chmod u=rw,go= "$run_binary"

exec dosbox-x \
    -conf analysis/config/dosbox-x.conf \
    -nopromptfolder
