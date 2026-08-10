#!/usr/bin/env python3

"""Apply the size-preserving EDIT-GRAV-01 softened-gravity patch."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from spacewar_edit import (
    CodeBuilder,
    PatchError,
    PatchRegion,
    apply_regions,
    run_file_edit,
    sha256_hex,
)


GRAVITY_CS_OFFSET = 0x1E30
GRAVITY_REGION_SIZE = 0x0070
GRAVITY_STRENGTH = 0x00040000
GRAVITY_SOFTENING = 32
PLAYABLE_X = range(8, 632)
PLAYABLE_Y = range(8, 192)

# CS:1E30..1E95 is the original routine and helper. The following ten bytes,
# CS:1E96..1E9F, are zero and have no observed incoming control-flow reference.
# The next known routine starts at CS:1EA0.
EXPECTED_GRAVITY_REGION = bytes.fromhex(
    "8b841c0d2d3f01781d8b943c0d83ea63"
    "780ae84000f7dbf7d9eb2390f7dae834"
    "00f7dbeb1990f7d88b943c0d83ea6378"
    "08e82100f7d9eb0690f7dae817008bc3"
    "990184dc0d11949c0d8bc1990184fc0d"
    "1194bc0dc38bd8d1e3d1e3d1e38bcad1"
    "e1d1e1d1e1c300000000000000000000"
)


def approximate_radius(x_magnitude: int, y_magnitude: int) -> int:
    high = max(x_magnitude, y_magnitude)
    low = min(x_magnitude, y_magnitude)
    return high + low // 2


def acceleration_component(magnitude: int, denominator: int) -> int:
    scale = GRAVITY_STRENGTH // denominator
    return magnitude * scale // denominator


def validate_gravity_model() -> tuple[int, int]:
    if not 1 <= GRAVITY_SOFTENING <= 0x7F:
        raise PatchError("gravity softening must fit the compact positive byte encoding")
    if GRAVITY_STRENGTH & 0xFFFF:
        raise PatchError("gravity strength must have a zero low word")
    strength_high = GRAVITY_STRENGTH >> 16
    if not 0 < strength_high < GRAVITY_SOFTENING:
        raise PatchError("gravity strength would overflow the first unsigned division")

    maximum_scale = 0
    maximum_acceleration = 0
    for x in PLAYABLE_X:
        x_magnitude = abs(319 - x)
        for y in PLAYABLE_Y:
            y_magnitude = abs(99 - y)
            denominator = (
                approximate_radius(x_magnitude, y_magnitude)
                + GRAVITY_SOFTENING
            )
            scale = GRAVITY_STRENGTH // denominator
            maximum_scale = max(maximum_scale, scale)
            for magnitude in (x_magnitude, y_magnitude):
                product = magnitude * scale
                if product > 0xFFFFFFFF:
                    raise PatchError("gravity multiply would overflow DX:AX")
                acceleration = acceleration_component(magnitude, denominator)
                maximum_acceleration = max(maximum_acceleration, acceleration)
                if acceleration > 0x7FFF:
                    raise PatchError("gravity component would overflow a signed word")
    return maximum_scale, maximum_acceleration


def build_gravity_code() -> bytes:
    maximum_scale, maximum_acceleration = validate_gravity_model()
    if maximum_scale > 0xFFFF or maximum_acceleration > 0x7FFF:
        raise AssertionError("validated gravity bounds are inconsistent")

    strength_high = GRAVITY_STRENGTH >> 16
    builder = CodeBuilder(GRAVITY_CS_OFFSET)

    # Preserve the caller's BP and DI. BL records the original component signs
    # while AX and DX are converted to unsigned magnitudes toward the center.
    builder.emit(0x55)                         # push bp
    builder.emit(0x57)                         # push di
    builder.emit(0x31, 0xDB)                   # xor bx, bx
    builder.emit(0xB8, 0x3F, 0x01)             # mov ax, 319
    builder.emit(0x2B, 0x84, 0x1C, 0x0D)       # sub ax, [si+0d1ch]
    builder.branch8(0x79, "x_positive")        # jns x_positive
    builder.emit(0xF7, 0xD8)                   # neg ax
    builder.emit(0xFE, 0xC3)                   # inc bl
    builder.label("x_positive")
    builder.emit(0xBA, 0x63, 0x00)             # mov dx, 99
    builder.emit(0x2B, 0x94, 0x3C, 0x0D)       # sub dx, [si+0d3ch]
    builder.branch8(0x79, "y_positive")        # jns y_positive
    builder.emit(0xF7, 0xDA)                   # neg dx
    builder.emit(0x80, 0xCB, 0x02)             # or bl, 2
    builder.label("y_positive")
    builder.emit(0x53)                         # push bx
    builder.emit(0x50)                         # push ax
    builder.emit(0x52)                         # push dx

    # Approximate radius as max(|dx|, |dy|) + floor(min(|dx|, |dy|) / 2).
    builder.emit(0x39, 0xD0)                   # cmp ax, dx
    builder.branch8(0x73, "have_max")          # jae have_max
    builder.emit(0x92)                         # xchg ax, dx
    builder.label("have_max")
    builder.emit(0xD1, 0xEA)                   # shr dx, 1
    builder.emit(0x01, 0xD0)                   # add ax, dx
    builder.emit(0x83, 0xC0, GRAVITY_SOFTENING)  # add ax, softening
    builder.emit(0x89, 0xC5)                   # mov bp, ax

    # scale = floor(strength / denominator), with strength in DX:AX.
    builder.emit(0x31, 0xC0)                   # xor ax, ax
    builder.emit(0xBA, strength_high & 0xFF, strength_high >> 8)
    builder.emit(0xF7, 0xF5)                   # div bp
    builder.emit(0x89, 0xC7)                   # mov di, ax

    # Each unsigned component becomes floor(magnitude * scale / denominator).
    builder.emit(0x59)                         # pop cx
    builder.emit(0x58)                         # pop ax
    builder.emit(0xF7, 0xE7)                   # mul di
    builder.emit(0xF7, 0xF5)                   # div bp
    builder.emit(0x89, 0xC3)                   # mov bx, ax
    builder.emit(0x89, 0xC8)                   # mov ax, cx
    builder.emit(0xF7, 0xE7)                   # mul di
    builder.emit(0xF7, 0xF5)                   # div bp
    builder.emit(0x89, 0xC1)                   # mov cx, ax

    # Restore direction toward the planet and add signed components to the
    # existing split 16.16 velocity words.
    builder.emit(0x58)                         # pop ax
    builder.emit(0xA8, 0x01)                   # test al, 1
    builder.branch8(0x74, "x_signed")          # jz x_signed
    builder.emit(0xF7, 0xDB)                   # neg bx
    builder.label("x_signed")
    builder.emit(0xA8, 0x02)                   # test al, 2
    builder.branch8(0x74, "y_signed")          # jz y_signed
    builder.emit(0xF7, 0xD9)                   # neg cx
    builder.label("y_signed")
    builder.emit(0x89, 0xD8)                   # mov ax, bx
    builder.emit(0x99)                         # cwd
    builder.emit(0x01, 0x84, 0xDC, 0x0D)       # add [si+0ddch], ax
    builder.emit(0x11, 0x94, 0x9C, 0x0D)       # adc [si+0d9ch], dx
    builder.emit(0x89, 0xC8)                   # mov ax, cx
    builder.emit(0x99)                         # cwd
    builder.emit(0x01, 0x84, 0xFC, 0x0D)       # add [si+0dfch], ax
    builder.emit(0x11, 0x94, 0xBC, 0x0D)       # adc [si+0dbch], dx
    builder.emit(0x5F)                         # pop di
    builder.emit(0x5D)                         # pop bp
    builder.emit(0xC3)                         # ret

    code, addresses = builder.finish()
    if addresses.get("x_positive") != 0x1E41:
        raise PatchError("gravity X-sign layout changed unexpectedly")
    if addresses.get("y_positive") != 0x1E4F:
        raise PatchError("gravity Y-sign layout changed unexpectedly")
    if len(code) != 0x006F:
        raise PatchError(f"expected 111 gravity bytes, got {len(code)}")
    if len(code) >= GRAVITY_REGION_SIZE:
        raise PatchError("gravity code no longer leaves its final guard byte empty")
    if len(EXPECTED_GRAVITY_REGION) != GRAVITY_REGION_SIZE:
        raise AssertionError("original gravity ownership guard has the wrong size")
    if EXPECTED_GRAVITY_REGION[-1] != 0:
        raise AssertionError("final adjacent guard byte is not zero")
    return code


def patch_bytes(data: bytes) -> bytes:
    code = build_gravity_code()
    region = PatchRegion.at_cs(
        "gravity routine and adjacent internal padding",
        GRAVITY_CS_OFFSET,
        EXPECTED_GRAVITY_REGION[:len(code)],
        code,
    )
    return apply_regions(data, (region,))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply EDIT-GRAV-01 to the exact investigated executable without "
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
    patched = run_file_edit(
        args.input_exe,
        args.output_exe,
        patch_bytes,
        force=args.force,
    )

    _, maximum_acceleration = validate_gravity_model()
    print("EDIT-GRAV-01 input validation: passed")
    print("physical size preserved: 0x5800 bytes")
    print("gravity code range: CS:1E30..1E9E (111 bytes)")
    print("unused adjacent padding: CS:1E9F (1 byte)")
    print(f"gravity strength: {GRAVITY_STRENGTH}")
    print(f"softening radius: {GRAVITY_SOFTENING}")
    print(f"maximum validated component: {maximum_acceleration}")
    print(f"patched SHA-256: {sha256_hex(patched)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
