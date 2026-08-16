#!/usr/bin/env python3

"""Build an ignored full-speed ghost-lifecycle trace executable."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

from spacewar_edit import (
    CODE_FILE_BASE,
    DECLARED_FILE_SIZE,
    EXPECTED_FILE_SIZE,
    PADDING_CS_OFFSET,
    PatchError,
    PatchRegion,
    CodeBuilder,
    apply_exact_image_extension,
    near_call,
    run_file_edit,
    sha256_hex,
)


GRAVITY_SHA256 = "a8be13c10e4440615692b1a4dd580a9569cfc8a6178f7f9f434c0b0ea8bc8d50"

TRACE_CODE_CS = PADDING_CS_OFFSET
TRACE_HEADER_CS = 0x2E00
TRACE_RECORDS_CS = 0x2E10
TRACE_VERSION = 1
TRACE_RECORD_SIZE = 24
TRACE_CAPACITY = 2048
TRACE_DUMP_SIZE = 0xC010
TRACE_END_CS = TRACE_RECORDS_CS + TRACE_RECORD_SIZE * TRACE_CAPACITY

HEADER_WRITE_INDEX = TRACE_HEADER_CS + 0x0A
HEADER_NEXT_SEQUENCE = TRACE_HEADER_CS + 0x0C
HEADER_WRAPPED = TRACE_HEADER_CS + 0x0E
HEADER_FROZEN = TRACE_HEADER_CS + 0x0F

EVENT_HYPERSPACE_ENTRY = 1
EVENT_HYPERSPACE_TICK = 2
EVENT_HYPERSPACE_COMPLETION = 3
EVENT_SHIP_XOR = 4
EVENT_RENDER_SNAPSHOT = 5

LEFT_SLOT = 0x00
RIGHT_SLOT = 0x10


def emit_word(builder: CodeBuilder, value: int) -> None:
    if not 0 <= value <= 0xFFFF:
        raise PatchError("trace word is outside 0000..FFFF")
    builder.emit(value & 0xFF, value >> 8)


def emit_mov_ax_imm(builder: CodeBuilder, value: int) -> None:
    builder.emit(0xB8)
    emit_word(builder, value)


def emit_call_trace(builder: CodeBuilder, event: int, slot: int) -> None:
    if event == 0 or slot not in (LEFT_SLOT, RIGHT_SLOT):
        raise PatchError("invalid trace event or ship slot")
    builder.emit(0x50)  # push ax
    emit_mov_ax_imm(builder, event | (slot << 8))
    builder.call16("trace_record")
    builder.emit(0x58)  # pop ax


def emit_cs_absolute(builder: CodeBuilder, opcode: tuple[int, ...], address: int) -> None:
    builder.emit(0x2E, *opcode)
    emit_word(builder, address)


def build_trace_code() -> tuple[bytes, dict[str, int]]:
    builder = CodeBuilder(TRACE_CODE_CS)

    builder.label("left_entry")
    builder.emit(0xFE, 0x06, 0x60, 0x00)  # inc byte [0060]
    builder.emit(0x80, 0x0E, 0x90, 0x22, 0x10)  # or byte [2290],10
    emit_call_trace(builder, EVENT_HYPERSPACE_ENTRY, LEFT_SLOT)
    builder.emit(0xC3)

    builder.label("right_entry")
    builder.emit(0xFE, 0x06, 0x61, 0x00)
    builder.emit(0x80, 0x0E, 0x90, 0x22, 0x10)
    emit_call_trace(builder, EVENT_HYPERSPACE_ENTRY, RIGHT_SLOT)
    builder.emit(0xC3)

    builder.label("left_tick")
    builder.emit(0xBE, 0x00, 0x00, 0xB9, 0x20, 0x00)
    emit_call_trace(builder, EVENT_HYPERSPACE_TICK, LEFT_SLOT)
    builder.emit(0xC3)

    builder.label("right_tick")
    builder.emit(0xBE, 0x40, 0x00, 0xB9, 0x20, 0x00)
    emit_call_trace(builder, EVENT_HYPERSPACE_TICK, RIGHT_SLOT)
    builder.emit(0xC3)

    builder.label("left_completion")
    builder.emit(0xBE, 0x00, 0x00, 0xB9, 0x20, 0x00)
    emit_call_trace(builder, EVENT_HYPERSPACE_COMPLETION, LEFT_SLOT)
    builder.emit(0xC3)

    builder.label("right_completion")
    builder.emit(0xBE, 0x40, 0x00, 0xB9, 0x20, 0x00)
    emit_call_trace(builder, EVENT_HYPERSPACE_COMPLETION, RIGHT_SLOT)
    builder.emit(0xC3)

    builder.label("left_ship_xor")
    builder.emit(0xBE, 0x00, 0x00, 0xBD, 0x40, 0x13)
    emit_call_trace(builder, EVENT_SHIP_XOR, LEFT_SLOT)
    builder.emit(0xC3)

    builder.label("right_ship_xor")
    builder.emit(0xBE, 0x10, 0x00, 0xBD, 0x40, 0x15)
    emit_call_trace(builder, EVENT_SHIP_XOR, RIGHT_SLOT)
    builder.emit(0xC3)

    builder.label("render_snapshot")
    builder.emit(0xC6, 0x84, 0x1C, 0x0E, 0x00)  # mov byte [si+0e1c],0
    builder.emit(0x9C)  # preserve the CLI-region flags across slot selection
    builder.emit(0x83, 0xFE, LEFT_SLOT)
    builder.branch8(0x75, "snapshot_check_right")
    builder.emit(0x9D)
    emit_call_trace(builder, EVENT_RENDER_SNAPSHOT, LEFT_SLOT)
    builder.emit(0xC3)
    builder.label("snapshot_check_right")
    builder.emit(0x83, 0xFE, RIGHT_SLOT)
    builder.branch8(0x75, "snapshot_untraced")
    builder.emit(0x9D)
    emit_call_trace(builder, EVENT_RENDER_SNAPSHOT, RIGHT_SLOT)
    builder.emit(0xC3)
    builder.label("snapshot_untraced")
    builder.emit(0x9D, 0xC3)

    # Callers pass AL=event and AH=ship slot. Reserve a record while interrupts
    # are masked, restore the caller's IF state, fill the record, and commit by
    # writing the nonzero event byte last. A timer interrupt can therefore nest
    # safely during the longer record-fill portion without sharing a slot.
    builder.label("trace_record")
    builder.emit(0x9C, 0xFA)  # pushf; cli
    builder.emit(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x55)
    builder.emit(0x89, 0xE5)  # mov bp,sp

    emit_cs_absolute(builder, (0x80, 0x3E), HEADER_FROZEN)
    builder.emit(0x00)  # cmp byte cs:[frozen],0
    builder.branch8(0x74, "trace_active")
    builder.jump16("trace_restore")

    builder.label("trace_active")
    emit_cs_absolute(builder, (0x8B, 0x1E), HEADER_WRITE_INDEX)
    builder.emit(0x89, 0xDA)  # mov dx,bx
    builder.emit(0x89, 0xDF)  # mov di,bx
    builder.emit(0xB1, 0x04, 0xD3, 0xE7)  # mov cl,4; shl di,cl
    builder.emit(0xB1, 0x03, 0xD3, 0xE3)  # mov cl,3; shl bx,cl
    builder.emit(0x01, 0xDF)  # add di,bx
    builder.emit(0x81, 0xC7)
    emit_word(builder, TRACE_RECORDS_CS)
    builder.emit(0x2E, 0xC6, 0x45, 0x02, 0x00)  # event=0: incomplete

    emit_cs_absolute(builder, (0xA1,), HEADER_NEXT_SEQUENCE)
    builder.emit(0x2E, 0x89, 0x05)  # mov cs:[di],ax
    builder.emit(0x40)
    emit_cs_absolute(builder, (0xA3,), HEADER_NEXT_SEQUENCE)

    builder.emit(0x42)  # inc dx
    builder.emit(0x81, 0xE2, 0xFF, 0x07)  # and dx,07ff
    emit_cs_absolute(builder, (0x89, 0x16), HEADER_WRITE_INDEX)
    builder.emit(0x09, 0xD2)  # or dx,dx
    builder.branch8(0x75, "index_updated")
    emit_cs_absolute(builder, (0xC6, 0x06), HEADER_WRAPPED)
    builder.emit(0x01)
    builder.label("index_updated")

    builder.emit(0xFF, 0x76, 0x0E, 0x9D)  # push word [bp+0e]; popf

    builder.emit(0x8B, 0x46, 0x0C)  # passed event/slot
    builder.emit(0x2E, 0x88, 0x65, 0x03)  # side at record+3
    builder.emit(0xA0, 0x80, 0x10, 0x2E, 0x88, 0x45, 0x04)
    builder.emit(0xA0, 0x60, 0x00, 0x2E, 0x88, 0x45, 0x05)
    builder.emit(0xA0, 0x61, 0x00, 0x2E, 0x88, 0x45, 0x06)

    builder.emit(0x8B, 0x46, 0x0C, 0x8A, 0xC4, 0x30, 0xE4, 0x89, 0xC6)
    for source, destination in (
        (0x0CBC, 0x07),
        (0x0E1C, 0x08),
        (0x0E3C, 0x09),
        (0x0E5C, 0x0A),
        (0x0E7C, 0x0B),
        (0x0EBC, 0x0C),
        (0x0EDC, 0x0D),
    ):
        builder.emit(0x8A, 0x84)
        emit_word(builder, source)
        builder.emit(0x2E, 0x88, 0x45, destination)

    builder.emit(0x8B, 0x46, 0x0E, 0x2E, 0x89, 0x45, 0x0E)
    for source, destination in (
        (0x0D1C, 0x10),
        (0x0D3C, 0x12),
        (0x0D5C, 0x14),
        (0x0D7C, 0x16),
    ):
        builder.emit(0x8B, 0x84)
        emit_word(builder, source)
        builder.emit(0x2E, 0x89, 0x45, destination)

    builder.emit(0x8B, 0x46, 0x0C, 0x2E, 0x88, 0x45, 0x02)  # commit event

    builder.label("trace_restore")
    builder.emit(0x5D, 0x5F, 0x5E, 0x5A, 0x59, 0x5B, 0x58, 0x9D, 0xC3)

    code, addresses = builder.finish()
    if len(code) > TRACE_HEADER_CS - TRACE_CODE_CS:
        raise PatchError("trace code overlaps the fixed trace header")
    return code, addresses


def hook_region(
    name: str,
    site: int,
    expected_hex: str,
    target: int,
) -> PatchRegion:
    expected = bytes.fromhex(expected_hex)
    if len(expected) < 3:
        raise PatchError(f"trace hook is too short: {name}")
    replacement = near_call(site, target) + b"\x90" * (len(expected) - 3)
    return PatchRegion.at_cs(name, site, expected, replacement)


def trace_header() -> bytes:
    return struct.pack(
        "<4sHHHHHBB",
        b"GHST",
        TRACE_VERSION,
        TRACE_RECORD_SIZE,
        TRACE_CAPACITY,
        0,
        0,
        0,
        0,
    )


def patch_bytes(data: bytes) -> bytes:
    code, addresses = build_trace_code()
    regions = (
        hook_region("render snapshot trace", 0x0248, "c6841c0e00", addresses["render_snapshot"]),
        hook_region("left hyperspace entry trace", 0x074F, "fe066000800e902210", addresses["left_entry"]),
        hook_region("right hyperspace entry trace", 0x07B2, "fe066100800e902210", addresses["right_entry"]),
        hook_region("right ship XOR trace", 0x1B96, "be1000bd4015", addresses["right_ship_xor"]),
        hook_region("left ship XOR trace", 0x1B9F, "be0000bd4013", addresses["left_ship_xor"]),
        hook_region("left hyperspace tick trace", 0x25AF, "be0000b92000", addresses["left_tick"]),
        hook_region("left hyperspace completion trace", 0x2630, "be0000b92000", addresses["left_completion"]),
        hook_region("right hyperspace tick trace", 0x26B1, "be4000b92000", addresses["right_tick"]),
        hook_region("right hyperspace completion trace", 0x2732, "be4000b92000", addresses["right_completion"]),
    )

    code_area = bytearray(TRACE_HEADER_CS - TRACE_CODE_CS)
    code_area[: len(code)] = code
    tail = bytes(code_area) + trace_header() + bytes(TRACE_RECORD_SIZE * TRACE_CAPACITY)
    if len(tail) != TRACE_END_CS - TRACE_CODE_CS:
        raise AssertionError("trace image-tail size is inconsistent")

    output = apply_exact_image_extension(
        data,
        regions,
        tail,
        expected_sha256=GRAVITY_SHA256,
        expected_file_size=EXPECTED_FILE_SIZE,
        expected_declared_size=DECLARED_FILE_SIZE,
        tail_file_offset=DECLARED_FILE_SIZE,
        code_file_base=CODE_FILE_BASE,
    )
    if output[CODE_FILE_BASE + TRACE_HEADER_CS : CODE_FILE_BASE + TRACE_RECORDS_CS] != trace_header():
        raise AssertionError("trace header was not emitted at its guarded location")
    if len(output) != CODE_FILE_BASE + TRACE_END_CS:
        raise AssertionError("expanded trace image has an unexpected size")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_exe", type=Path)
    parser.add_argument("output_exe", type=Path)
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    patched = run_file_edit(
        args.input_exe,
        args.output_exe,
        patch_bytes,
        force=args.force,
    )
    code, _ = build_trace_code()
    print("ghost trace input validation: passed")
    print(f"trace code: CS:{TRACE_CODE_CS:04X}..{TRACE_CODE_CS + len(code) - 1:04X}")
    print(f"trace header: CS:{TRACE_HEADER_CS:04X}..{TRACE_RECORDS_CS - 1:04X}")
    print(f"trace records: {TRACE_CAPACITY} x {TRACE_RECORD_SIZE} bytes")
    print(f"trace dump: CS:{TRACE_HEADER_CS:04X} length {TRACE_DUMP_SIZE:04X}")
    print(f"physical size: 0x{len(patched):X} bytes")
    print(f"instrumented SHA-256: {sha256_hex(patched)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
