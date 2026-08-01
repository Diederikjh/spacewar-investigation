#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

source_binary='analysis/work/Spacewar1985.exe'
run_dir='analysis/work/dosbox-run'
trace_dir='analysis/traces/phase3'
break_binary="$run_dir/SPACEBRK.EXE"
debugger_binary=${SPACEWAR_DOSBOX_DEBUG_BIN:-dosbox-debug}

test -f "$source_binary"
command -v radare2 >/dev/null
command -v "$debugger_binary" >/dev/null
command -v xxd >/dev/null

mkdir -p "$run_dir" "$trace_dir"
cp -- "$source_binary" "$break_binary"
chmod u=rw,go= "$break_binary"

# The MZ entry point is at file offset 0x2CB0. The temporary INT 3 is
# restored in guest memory before execution continues from CS:0000.
entry_byte=$(xxd -p -s 0x2cb0 -l 1 "$break_binary")
test "$entry_byte" = '8c'
radare2 -2 -q -w -c 's 0x2cb0; wx cc' "$break_binary"

exec "$debugger_binary" -conf analysis/config/dosbox-debug.conf
