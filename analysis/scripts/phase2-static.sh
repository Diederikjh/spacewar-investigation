#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

binary='analysis/work/Spacewar1985.exe'
output_dir='analysis/work/phase2-static'

test -f "$binary"
command -v ndisasm >/dev/null
command -v rabin2 >/dev/null
command -v radare2 >/dev/null

mkdir -p "$output_dir"

# The MZ header is 0x200 bytes and the entry is load-module offset 0x2AB0.
# This linear sweep is a navigation aid only: inline strings and bitmap data are
# deliberately interleaved with code and must not be interpreted as instructions.
ndisasm -b 16 -e 0x2CB0 -o 0x2AB0 "$binary" \
    > "$output_dir/linear-from-entry.txt"

{
    rabin2 -I "$binary"
    rabin2 -e "$binary"
    rabin2 -R "$binary"
} > "$output_dir/loader-cross-check.txt"

disassemble_region() {
    local output_name=$1
    local start=$2
    local byte_count=$3

    radare2 -2 -q \
        -e scr.color=0 \
        -e asm.comments=false \
        -e asm.lines=false \
        -c "s $start; pD $byte_count" \
        "$binary" > "$output_dir/$output_name.txt"
}

disassemble_region startup 0x2AB0 0xBC
disassemble_region game-foreground 0x2B6C 0x884
disassemble_region frontend 0x33F0 0xF5D
disassemble_region drawing 0x45A0 0x3B0
disassemble_region interrupts 0x4950 0x140
disassemble_region game-timer 0x4DED 0x470
disassemble_region sound-random-projectiles 0x5260 0x334

printf 'Phase 2 local static outputs written under %s\n' "$output_dir"
