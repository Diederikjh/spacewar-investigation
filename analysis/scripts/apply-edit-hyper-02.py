#!/usr/bin/env python3

"""Apply the size-preserving EDIT-HYPER-02 round-start counter reset."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from spacewar_edit import (
    CodeBuilder,
    DECLARED_FILE_SIZE,
    EXPECTED_FILE_SIZE,
    PatchError,
    PatchRegion,
    apply_regions,
    mz_declared_size,
    near_call,
    run_file_edit,
    sha256_hex,
)


ROUND_START_HOOK_CS = 0x00BF
RESET_HELPER_CS = 0x28C5
RESET_HELPER_LIMIT_CS = 0x28D0
HYPERSPACE_COUNTER_WORD = 0x0060
PAUSE_BYTE = 0x0170

EXPECTED_ROUND_START = bytes.fromhex("c6 06 70 01 00")
EXPECTED_INTERNAL_CAVE = b"\x00" * (RESET_HELPER_LIMIT_CS - RESET_HELPER_CS)


def build_reset_helper() -> bytes:
    builder = CodeBuilder(RESET_HELPER_CS)
    builder.emit(0x31, 0xC0)  # xor ax, ax
    builder.emit(0xA2, PAUSE_BYTE & 0xFF, PAUSE_BYTE >> 8)  # mov [0170h], al
    builder.emit(
        0xA3,
        HYPERSPACE_COUNTER_WORD & 0xFF,
        HYPERSPACE_COUNTER_WORD >> 8,
    )  # mov [0060h], ax
    builder.emit(0xC3)  # ret
    code, addresses = builder.finish()

    if addresses:
        raise PatchError("counter-reset helper unexpectedly contains labels")
    if len(code) != 9:
        raise PatchError(f"expected 9 helper bytes, got {len(code)}")
    if RESET_HELPER_CS + len(code) >= RESET_HELPER_LIMIT_CS:
        raise PatchError("counter-reset helper would consume the cave guard bytes")
    return code


def patch_regions() -> tuple[PatchRegion, ...]:
    helper = build_reset_helper()
    hook = near_call(ROUND_START_HOOK_CS, RESET_HELPER_CS) + b"\x90\x90"
    if len(hook) != len(EXPECTED_ROUND_START):
        raise AssertionError("round-start hook size changed")

    return (
        PatchRegion.at_cs(
            "round-start pause-clear hook",
            ROUND_START_HOOK_CS,
            EXPECTED_ROUND_START,
            hook,
        ),
        PatchRegion.at_cs(
            "internal counter-reset helper cave",
            RESET_HELPER_CS,
            EXPECTED_INTERNAL_CAVE,
            helper + b"\x00" * (len(EXPECTED_INTERNAL_CAVE) - len(helper)),
        ),
    )


def patch_bytes(data: bytes) -> bytes:
    patched = apply_regions(data, patch_regions())
    if len(patched) != EXPECTED_FILE_SIZE:
        raise AssertionError("EDIT-HYPER-02 changed the physical file size")
    if mz_declared_size(patched) != DECLARED_FILE_SIZE:
        raise AssertionError("EDIT-HYPER-02 changed the MZ-declared size")
    return patched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply EDIT-HYPER-02 to the exact investigated executable without "
            "increasing its physical or MZ-declared size."
        )
    )
    parser.add_argument("input_exe", type=Path)
    parser.add_argument("output_exe", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    patched = run_file_edit(
        args.input_exe,
        args.output_exe,
        patch_bytes,
        force=args.force,
    )

    print("EDIT-HYPER-02 input validation: passed")
    print("physical size preserved: 0x5800 bytes")
    print("MZ-declared size preserved: 0x5794 bytes")
    print("round-start hook: CS:00BF..00C3")
    print("counter-reset helper: CS:28C5..28CD")
    print("unused cave guard: CS:28CE..28CF")
    print("cleared state: DS:0060 word (left/right hyperspace counters)")
    print(f"patched SHA-256: {sha256_hex(patched)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
