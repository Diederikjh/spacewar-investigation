#!/usr/bin/env python3

"""Apply the size-preserving EDIT-CPU-05 wrapped-aim patch."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from spacewar_edit import (
    CodeBuilder,
    PADDING_CS_OFFSET,
    PADDING_FILE_OFFSET,
    PADDING_SIZE,
    PatchError,
    PatchRegion,
    apply_regions,
    near_call,
    run_file_edit,
    sha256_hex,
)


def build_helper_code() -> tuple[bytes, dict[str, int]]:
    builder = CodeBuilder(PADDING_CS_OFFSET)

    # AX contains a raw delta. Select the relevant world extent and return
    # its shortest wrapped absolute magnitude in AX. BX and DX are scratch;
    # the left policy overwrites both before either value is next consumed.
    builder.label("wrap_abs_x")
    builder.emit(0xBB, 0x80, 0x02)       # mov bx, 640
    builder.branch8(0xEB, "wrap_abs")    # jmp short wrap_abs
    builder.label("wrap_abs_y")
    builder.emit(0xBB, 0xC8, 0x00)       # mov bx, 200
    builder.label("wrap_abs")
    builder.emit(0x8B, 0xD3)             # mov dx, bx
    builder.emit(0xD1, 0xEA)             # shr dx, 1
    builder.emit(0x3B, 0xC2)             # cmp ax, dx
    builder.branch8(0x7E, "abs_low")     # jle abs_low
    builder.emit(0x29, 0xD8)             # sub ax, bx
    builder.branch8(0xEB, "absolute")    # jmp short absolute
    builder.label("abs_low")
    builder.emit(0xF7, 0xDA)             # neg dx
    builder.emit(0x3B, 0xC2)             # cmp ax, dx
    builder.branch8(0x7D, "absolute")    # jge absolute
    builder.emit(0x01, 0xD8)             # add ax, bx
    builder.label("absolute")
    builder.emit(0x0B, 0xC0)             # or ax, ax
    builder.branch8(0x79, "abs_done")    # jns abs_done
    builder.emit(0xF7, 0xD8)             # neg ax
    builder.label("abs_done")
    builder.emit(0xC3)                   # ret

    # CX is the raw target-minus-origin X delta; DX is the corresponding Y
    # delta. Normalize both in place while preserving the exact half-world
    # ties (+/-320 and +/-100) used by the executable model.
    builder.label("wrap_signed_xy")
    builder.emit(0x81, 0xF9, 0x40, 0x01) # cmp cx, 320
    builder.branch8(0x7E, "x_low")       # jle x_low
    builder.emit(0x81, 0xE9, 0x80, 0x02) # sub cx, 640
    builder.branch8(0xEB, "x_done")      # jmp short x_done
    builder.label("x_low")
    builder.emit(0x81, 0xF9, 0xC0, 0xFE) # cmp cx, -320
    builder.branch8(0x7D, "x_done")      # jge x_done
    builder.emit(0x81, 0xC1, 0x80, 0x02) # add cx, 640
    builder.label("x_done")
    builder.emit(0x83, 0xFA, 0x64)       # cmp dx, 100
    builder.branch8(0x7E, "y_low")       # jle y_low
    builder.emit(0x81, 0xEA, 0xC8, 0x00) # sub dx, 200
    builder.branch8(0xEB, "y_done")      # jmp short y_done
    builder.label("y_low")
    builder.emit(0x83, 0xFA, 0x9C)       # cmp dx, -100
    builder.branch8(0x7D, "y_done")      # jge y_done
    builder.emit(0x81, 0xC2, 0xC8, 0x00) # add dx, 200
    builder.label("y_done")
    builder.emit(0xC3)                   # ret

    # These wrappers replay the displaced Y-delta instructions, normalize
    # the already calculated X delta and the new Y delta, then return to the
    # original bearing code.
    builder.label("left_wrap_xy")
    builder.emit(0x8B, 0x94, 0x3C, 0x0D) # mov dx, [si+0d3ch]
    builder.emit(0x2B, 0x16, 0x3C, 0x0D) # sub dx, [0d3ch]
    builder.call16("wrap_signed_xy")
    builder.emit(0xC3)                   # ret

    builder.label("right_wrap_xy")
    builder.emit(0x8B, 0x16, 0x3C, 0x0D) # mov dx, [0d3ch]
    builder.emit(0x2B, 0x16, 0x4C, 0x0D) # sub dx, [0d4ch]
    builder.call16("wrap_signed_xy")
    builder.emit(0xC3)                   # ret

    code, addresses = builder.finish()
    expected_addresses = {
        "wrap_abs_x": 0x2AE4,
        "wrap_abs_y": 0x2AE9,
        "wrap_signed_xy": 0x2B07,
        "left_wrap_xy": 0x2B32,
        "right_wrap_xy": 0x2B3E,
    }
    for name, expected in expected_addresses.items():
        if addresses.get(name) != expected:
            raise PatchError(
                f"helper layout changed for {name}: "
                f"expected {expected:04X}, got {addresses.get(name, -1):04X}"
            )
    if len(code) != 0x66:
        raise PatchError(f"expected 102 helper bytes, got {len(code)}")
    if len(code) > PADDING_SIZE:
        raise PatchError("helper code would require executable file growth")
    return code, addresses


def build_patch_sites(addresses: dict[str, int]) -> tuple[PatchRegion, ...]:
    return (
        PatchRegion.at_cs(
            "left threat Y wrapping",
            0x03CF,
            bytes.fromhex("79 02 f7 d8"),
            near_call(0x03CF, addresses["wrap_abs_y"]) + b"\x90",
        ),
        PatchRegion.at_cs(
            "left threat X wrapping",
            0x03DF,
            bytes.fromhex("79 02 f7 d8"),
            near_call(0x03DF, addresses["wrap_abs_x"]) + b"\x90",
        ),
        PatchRegion.at_cs(
            "left bearing wrapping",
            0x03F2,
            bytes.fromhex("8b 94 3c 0d 2b 16 3c 0d"),
            near_call(0x03F2, addresses["left_wrap_xy"]) + b"\x90" * 5,
        ),
        PatchRegion.at_cs(
            "right bearing and proximity wrapping",
            0x05F1,
            bytes.fromhex("8b 16 3c 0d 2b 16 4c 0d"),
            near_call(0x05F1, addresses["right_wrap_xy"]) + b"\x90" * 5,
        ),
    )


def patch_bytes(data: bytes) -> bytes:
    helper_code, addresses = build_helper_code()
    sites = build_patch_sites(addresses)
    regions = sites + (
        PatchRegion(
            "MZ complete-final-page promotion",
            0x02,
            b"\x94\x01",
            b"\x00\x00",
        ),
        PatchRegion(
            "promoted helper area",
            PADDING_FILE_OFFSET,
            b"\x00" * PADDING_SIZE,
            helper_code + b"\x00" * (PADDING_SIZE - len(helper_code)),
        ),
    )
    return apply_regions(data, regions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply EDIT-CPU-05 to the exact investigated executable without "
            "increasing its physical size."
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
    input_path = args.input_exe
    output_path = args.output_exe

    patched = run_file_edit(
        input_path,
        output_path,
        patch_bytes,
        force=args.force,
    )

    print("EDIT-CPU-05 input validation: passed")
    print("physical size preserved: 0x5800 bytes")
    print("promoted helper range: CS:2AE4..2B49 (102 bytes)")
    print("unused promoted padding: CS:2B4A..2B4F (6 bytes)")
    print(f"patched SHA-256: {sha256_hex(patched)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
