#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

source_binary=${SPACEWAR_DEBUG_SOURCE:-analysis/work/Spacewar1985.exe}
run_dir='analysis/work/dosbox-run'
trace_dir='analysis/traces/phase3'
break_binary="$run_dir/SPACEBRK.EXE"
debugger_binary=${SPACEWAR_DOSBOX_DEBUG_BIN:-dosbox-debug}
session_pid_file=${SPACEWAR_DEBUG_PID_FILE:-}

test -f "$source_binary"
command -v radare2 >/dev/null
command -v "$debugger_binary" >/dev/null
command -v xxd >/dev/null

mkdir -p "$run_dir" "$trace_dir"
cp -- "$source_binary" "$break_binary"
chmod u=rw,go= "$break_binary"

# The MZ entry point is at file offset 0x2CB0. The temporary INT 03h is
# restored in guest memory before execution continues from CS:0000.
entry_bytes=$(xxd -p -s 0x2cb0 -l 2 "$break_binary")
test "$entry_bytes" = '8cd8'
radare2 -n -2 -q -w -c 's 0x2cb0; wx cd03' "$break_binary"
patched_entry_bytes=$(xxd -p -s 0x2cb0 -l 2 "$break_binary")
test "$patched_entry_bytes" = 'cd03'

if [[ -n $session_pid_file ]]; then
    if [[ ! $session_pid_file =~ ^analysis/work/[A-Za-z0-9_./-]+$ || $session_pid_file == *..* ]]; then
        printf 'error: debugger PID file must remain under analysis/work\n' >&2
        exit 2
    fi
    mkdir -p -- "$(dirname -- "$session_pid_file")"
    umask 077
    printf '%s\n' "$$" >"$session_pid_file"
fi

exec "$debugger_binary" -conf analysis/config/dosbox-debug.conf
