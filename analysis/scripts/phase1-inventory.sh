#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
analysis_dir=$(cd -- "$script_dir/.." && pwd)
project_dir=$(cd -- "$analysis_dir/.." && pwd)
cd -- "$project_dir"

original='artefact/Spacewar1985.exe'
working='analysis/work/Spacewar1985.exe'
inventory='analysis/inventory'
decoder='analysis/scripts/decode-mz.pl'
manifest='analysis/manifest.sha256'

test -f "$original"
mkdir -p "$inventory" "$(dirname -- "$working")"
cp --preserve=timestamps -- "$original" "$working"
chmod u=rw,go= "$working"

original_hash=$(sha256sum "$original" | awk '{print $1}')
working_hash=$(sha256sum "$working" | awk '{print $1}')
test "$original_hash" = "$working_hash"

{
    printf '%s  %s\n' "$original_hash" 'artefact/Spacewar1985.exe'
    printf '%s  %s\n' "$working_hash" 'analysis/work/Spacewar1985.exe'
} > "$manifest"

printf 'Platform: Ubuntu\n' > "$inventory/platform.txt"

{
    stat --printf='Path: %n\nSize: %s bytes\n' "$original"
    file -k "$original"
} > "$inventory/file.txt"

xxd -g 1 -l 256 "$working" > "$inventory/header.hex"
perl "$decoder" "$working" > "$inventory/header-report.txt"
objdump -x "$working" > "$inventory/objdump.txt" 2>&1 || true
strings -a -t x -n 4 "$working" > "$inventory/strings.txt"

header_paragraphs=$(od -An -tu2 -j 8 -N 2 "$working" | tr -d ' ')
initial_ip=$(od -An -tu2 -j 20 -N 2 "$working" | tr -d ' ')
initial_cs=$(od -An -tu2 -j 22 -N 2 "$working" | tr -d ' ')
entry_file_offset=$((header_paragraphs * 16 + initial_cs * 16 + initial_ip))
xxd -g 1 -s "$entry_file_offset" -l 512 "$working" > "$inventory/entry.hex"
objdump -D -b binary -m i8086 \
    --start-address="$entry_file_offset" \
    --stop-address="$((entry_file_offset + 1024))" \
    "$working" > "$inventory/entry-disassembly.txt"

declared_last_bytes=$(od -An -tu2 -j 2 -N 2 "$working" | tr -d ' ')
declared_pages=$(od -An -tu2 -j 4 -N 2 "$working" | tr -d ' ')
if ((declared_last_bytes == 0)); then
    declared_size=$((declared_pages * 512))
else
    declared_size=$(((declared_pages - 1) * 512 + declared_last_bytes))
fi
xxd -g 1 -s "$declared_size" "$working" > "$inventory/trailing-bytes.hex"

if ! strings -a -n 4 "$working" |
    grep -Eai 'LZEXE|PKLITE|EXEPACK|DIET|UPX|Microsoft|Borland|Turbo|Watcom|Quick[Cc]|runtime error' \
        > "$inventory/signature-clues.txt"; then
    printf 'No common compiler or executable-packer string signatures found.\n' \
        > "$inventory/signature-clues.txt"
fi

od -An -v -tu1 "$working" |
awk -v file_size="$(stat -c %s "$working")" '
    {
        for (i = 1; i <= NF; i++) {
            count[$i]++;
            total++;
            if ($i >= 32 && $i <= 126) printable++;
            if ($i == 0) zeros++;
        }
    }
    END {
        entropy = 0;
        used = 0;
        for (byte in count) {
            p = count[byte] / total;
            entropy -= p * log(p) / log(2);
            used++;
        }
        printf "File size: %d bytes\n", file_size;
        printf "Shannon entropy: %.4f bits/byte\n", entropy;
        printf "Distinct byte values: %d of 256\n", used;
        printf "Printable ASCII bytes: %d (%.2f%%)\n", printable, printable * 100 / total;
        printf "Zero bytes: %d (%.2f%%)\n", zeros, zeros * 100 / total;
    }
' > "$inventory/metrics.txt"

string_chars=$(strings -a -n 4 "$working" | awk '{total += length($0)} END {print total + 0}')
string_count=$(strings -a -n 4 "$working" | awk 'END {print NR + 0}')
{
    printf 'Extracted strings (minimum length 4): %d\n' "$string_count"
    printf 'Characters in extracted strings: %d\n' "$string_chars"
    awk -v chars="$string_chars" -v size="$(stat -c %s "$working")" \
        'BEGIN { printf "Approximate extracted-string density: %.2f%%\n", chars * 100 / size }'
} >> "$inventory/metrics.txt"

final_original_hash=$(sha256sum "$original" | awk '{print $1}')
test "$original_hash" = "$final_original_hash"

printf 'Phase 1 inventory complete; original hash unchanged: %s\n' "$original_hash"
