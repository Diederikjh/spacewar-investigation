#!/usr/bin/env python3

"""Apply the size-preserving EDIT-CPU-06 photon-leading patch."""

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


LEAD_TICKS = 64
PHASER_AXIS_LIMIT = 0x60
GRAVITY_MASK = 0x02


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def predicted_delta(
    current_delta: int,
    target_velocity_16_16: int,
    shooter_velocity_16_16: int,
) -> int:
    """Model one emitted 16-bit lead component."""

    relative = signed32(target_velocity_16_16 - shooter_velocity_16_16)
    displacement = (relative * LEAD_TICKS) >> 16
    return signed16(current_delta + displacement)


def signed32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def right_aim_deltas(
    current_x: int,
    current_y: int,
    target_velocity_x: int,
    target_velocity_y: int,
    shooter_velocity_x: int,
    shooter_velocity_y: int,
    *,
    gravity_enabled: bool,
) -> tuple[int, int]:
    """Model the prototype's gravity and phaser-range gates."""

    current_x = signed16(current_x)
    current_y = signed16(current_y)
    if gravity_enabled or (
        abs(current_x) < PHASER_AXIS_LIMIT
        and abs(current_y) < PHASER_AXIS_LIMIT
    ):
        return current_x, current_y
    return (
        predicted_delta(current_x, target_velocity_x, shooter_velocity_x),
        predicted_delta(current_y, target_velocity_y, shooter_velocity_y),
    )


def self_test_model() -> None:
    one = 1 << 16
    half = 1 << 15

    assert right_aim_deltas(95, 95, one, 0, 0, 0, gravity_enabled=False) == (
        95,
        95,
    )
    assert right_aim_deltas(96, 0, one, 0, 0, 0, gravity_enabled=False) == (
        160,
        0,
    )
    assert right_aim_deltas(96, 0, half, 0, 0, 0, gravity_enabled=False) == (
        128,
        0,
    )
    assert right_aim_deltas(96, 0, -half, 0, 0, 0, gravity_enabled=False) == (
        64,
        0,
    )
    assert right_aim_deltas(96, 0, one, 0, one, 0, gravity_enabled=False) == (
        96,
        0,
    )
    assert right_aim_deltas(96, 0, one, 0, 0, 0, gravity_enabled=True) == (
        96,
        0,
    )


def build_helper_code() -> tuple[bytes, dict[str, int]]:
    builder = CodeBuilder(PADDING_CS_OFFSET)

    # Begin with the original raw target-minus-shooter deltas. Leading is
    # deliberately bypassed under gravity and while both axes are within the
    # right policy's phaser range.
    builder.label("right_lead_deltas")
    builder.emit(0x8B, 0x0E, 0x1C, 0x0D)       # mov cx,[0d1c]
    builder.emit(0x2B, 0x0E, 0x2C, 0x0D)       # sub cx,[0d2c]
    builder.emit(0x8B, 0x16, 0x3C, 0x0D)       # mov dx,[0d3c]
    builder.emit(0x2B, 0x16, 0x4C, 0x0D)       # sub dx,[0d4c]
    builder.emit(0xF6, 0x06, 0x40, 0x20, GRAVITY_MASK)
    builder.branch8(0x75, "done")              # jnz done

    builder.emit(0x8B, 0xC1)                   # mov ax,cx
    builder.emit(0x0B, 0xC0)                   # or ax,ax
    builder.branch8(0x79, "x_absolute")        # jns x_absolute
    builder.emit(0xF7, 0xD8)                   # neg ax
    builder.label("x_absolute")
    builder.emit(0x3D, PHASER_AXIS_LIMIT, 0x00) # cmp ax,0060
    builder.branch8(0x73, "lead")              # jae lead

    builder.emit(0x8B, 0xC2)                   # mov ax,dx
    builder.emit(0x0B, 0xC0)                   # or ax,ax
    builder.branch8(0x79, "y_absolute")        # jns y_absolute
    builder.emit(0xF7, 0xD8)                   # neg ax
    builder.label("y_absolute")
    builder.emit(0x3D, PHASER_AXIS_LIMIT, 0x00) # cmp ax,0060
    builder.branch8(0x72, "done")              # jb done

    # A photon moves at approximately two pixels per timer tick relative to
    # its firing ship. Use a tunable 64-tick horizon. For each axis, subtract
    # the shooter's signed 16.16 velocity from the target's, then calculate
    # floor(relative_velocity * 64) exactly as high_word*64 + low_word/1024.
    # CX is saved because CL supplies the 8086 variable shift count.
    builder.label("lead")
    builder.emit(0x51)                         # push cx

    builder.emit(0xA1, 0xFC, 0x0D)             # mov ax,[0dfc]
    builder.emit(0x2B, 0x06, 0x0C, 0x0E)       # sub ax,[0e0c]
    builder.emit(0x8B, 0x1E, 0xBC, 0x0D)       # mov bx,[0dbc]
    builder.emit(0x1B, 0x1E, 0xCC, 0x0D)       # sbb bx,[0dcc]
    builder.emit(0xB1, 0x06)                   # mov cl,6
    builder.emit(0xD3, 0xE3)                   # shl bx,cl
    builder.emit(0xB1, 0x0A)                   # mov cl,10
    builder.emit(0xD3, 0xE8)                   # shr ax,cl
    builder.emit(0x03, 0xD8)                   # add bx,ax
    builder.emit(0x03, 0xD3)                   # add dx,bx

    builder.emit(0xA1, 0xDC, 0x0D)             # mov ax,[0ddc]
    builder.emit(0x2B, 0x06, 0xEC, 0x0D)       # sub ax,[0dec]
    builder.emit(0x8B, 0x1E, 0x9C, 0x0D)       # mov bx,[0d9c]
    builder.emit(0x1B, 0x1E, 0xAC, 0x0D)       # sbb bx,[0dac]
    builder.emit(0xB1, 0x06)                   # mov cl,6
    builder.emit(0xD3, 0xE3)                   # shl bx,cl
    builder.emit(0xB1, 0x0A)                   # mov cl,10
    builder.emit(0xD3, 0xE8)                   # shr ax,cl
    builder.emit(0x03, 0xD8)                   # add bx,ax
    builder.emit(0x59)                         # pop cx
    builder.emit(0x03, 0xCB)                   # add cx,bx

    builder.label("done")
    builder.emit(0x33, 0xDB)                   # xor bx,bx
    builder.emit(0xC3)                         # ret

    code, addresses = builder.finish()
    if addresses.get("right_lead_deltas") != PADDING_CS_OFFSET:
        raise PatchError("unexpected EDIT-CPU-06 helper entry")
    if len(code) != PADDING_SIZE:
        raise PatchError(
            f"expected {PADDING_SIZE} helper bytes, got {len(code)}"
        )
    return code, addresses


def patch_bytes(data: bytes) -> bytes:
    self_test_model()
    helper_code, addresses = build_helper_code()
    hook_expected = bytes.fromhex(
        "8b 0e 1c 0d 2b 0e 2c 0d 8b 16 3c 0d 2b 16 4c 0d"
    )
    hook_replacement = near_call(
        0x05E9,
        addresses["right_lead_deltas"],
    ) + b"\x90" * 13
    regions = (
        PatchRegion.at_cs(
            "right target-leading hook",
            0x05E9,
            hook_expected,
            hook_replacement,
        ),
        PatchRegion(
            "MZ complete-final-page promotion",
            0x02,
            b"\x94\x01",
            b"\x00\x00",
        ),
        PatchRegion(
            "promoted target-leading helper",
            PADDING_FILE_OFFSET,
            b"\x00" * PADDING_SIZE,
            helper_code,
        ),
    )
    return apply_regions(data, regions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply EDIT-CPU-06 to the exact investigated executable without "
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

    print("EDIT-CPU-06 input validation: passed")
    print("physical size preserved: 0x5800 bytes")
    print("lead horizon: 64 timer ticks")
    print("gravity behavior: original current-position aim")
    print("promoted helper range: CS:2AE4..2B4F (108 bytes)")
    print(f"patched SHA-256: {sha256_hex(patched)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
