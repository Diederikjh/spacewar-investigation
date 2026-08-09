#!/usr/bin/env python3

"""Apply the size-preserving EDIT-CPU-05 wrapped-aim patch."""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import stat
import struct
import sys


EXPECTED_SHA256 = "2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490"
EXPECTED_FILE_SIZE = 0x5800
DECLARED_FILE_SIZE = 0x5794
CODE_FILE_BASE = 0x2CB0
PADDING_FILE_OFFSET = 0x5794
PADDING_CS_OFFSET = 0x2AE4
PADDING_SIZE = 0x006C
CHECKSUM_OFFSET = 0x0012


class PatchError(RuntimeError):
    """Raised when an input or layout guard prevents a safe patch."""


class CodeBuilder:
    """Build the small 8086 helper block and resolve relative branches."""

    def __init__(self, base: int) -> None:
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str]] = []

    def emit(self, *values: int) -> None:
        self.code.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise PatchError(f"duplicate helper label: {name}")
        self.labels[name] = len(self.code)

    def branch8(self, opcode: int, target: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.code) - 1, 1, target))

    def call16(self, target: str) -> None:
        self.emit(0xE8, 0, 0)
        self.fixups.append((len(self.code) - 2, 2, target))

    def finish(self) -> tuple[bytes, dict[str, int]]:
        for operand_at, width, target_name in self.fixups:
            if target_name not in self.labels:
                raise PatchError(f"unknown helper label: {target_name}")
            target = self.base + self.labels[target_name]
            next_instruction = self.base + operand_at + width
            displacement = target - next_instruction
            if width == 1:
                if not -0x80 <= displacement <= 0x7F:
                    raise PatchError(f"short branch out of range: {target_name}")
                self.code[operand_at] = displacement & 0xFF
            else:
                if not -0x8000 <= displacement <= 0x7FFF:
                    raise PatchError(f"near call out of range: {target_name}")
                struct.pack_into("<h", self.code, operand_at, displacement)
        addresses = {
            name: self.base + offset for name, offset in self.labels.items()
        }
        return bytes(self.code), addresses


@dataclass(frozen=True)
class PatchSite:
    name: str
    cs_offset: int
    expected: bytes
    replacement: bytes

    @property
    def file_offset(self) -> int:
        return CODE_FILE_BASE + self.cs_offset


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


def near_call(site: int, target: int) -> bytes:
    displacement = target - (site + 3)
    if not -0x8000 <= displacement <= 0x7FFF:
        raise PatchError("hook target is outside 16-bit near-call range")
    return b"\xE8" + struct.pack("<h", displacement)


def build_patch_sites(addresses: dict[str, int]) -> tuple[PatchSite, ...]:
    return (
        PatchSite(
            "left threat Y wrapping",
            0x03CF,
            bytes.fromhex("79 02 f7 d8"),
            near_call(0x03CF, addresses["wrap_abs_y"]) + b"\x90",
        ),
        PatchSite(
            "left threat X wrapping",
            0x03DF,
            bytes.fromhex("79 02 f7 d8"),
            near_call(0x03DF, addresses["wrap_abs_x"]) + b"\x90",
        ),
        PatchSite(
            "left bearing wrapping",
            0x03F2,
            bytes.fromhex("8b 94 3c 0d 2b 16 3c 0d"),
            near_call(0x03F2, addresses["left_wrap_xy"]) + b"\x90" * 5,
        ),
        PatchSite(
            "right bearing and proximity wrapping",
            0x05F1,
            bytes.fromhex("8b 16 3c 0d 2b 16 4c 0d"),
            near_call(0x05F1, addresses["right_wrap_xy"]) + b"\x90" * 5,
        ),
    )


def word_sum(data: bytes | bytearray) -> int:
    if len(data) % 2:
        data = bytes(data) + b"\x00"
    return sum(struct.unpack(f"<{len(data) // 2}H", data)) & 0xFFFF


def validate_input(data: bytes) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise PatchError("input SHA-256 does not match the investigated executable")
    if len(data) != EXPECTED_FILE_SIZE:
        raise PatchError("input physical size is not exactly 0x5800 bytes")
    if data[:2] != b"MZ":
        raise PatchError("input does not have an MZ header")

    expected_fields = {
        0x02: 0x0194,
        0x04: 0x002C,
        0x08: 0x0020,
        0x0A: 0x0001,
        0x16: 0x02AB,
    }
    for offset, expected in expected_fields.items():
        actual = struct.unpack_from("<H", data, offset)[0]
        if actual != expected:
            raise PatchError(
                f"unexpected MZ field at header offset 0x{offset:02X}"
            )
    declared_size = (0x002C - 1) * 512 + 0x0194
    if declared_size != DECLARED_FILE_SIZE:
        raise AssertionError("declared-size constants are inconsistent")
    if any(data[PADDING_FILE_OFFSET:]):
        raise PatchError("trailing physical padding is not entirely zero")


def patch_bytes(data: bytes) -> bytes:
    validate_input(data)
    helper_code, addresses = build_helper_code()
    sites = build_patch_sites(addresses)
    output = bytearray(data)

    for site in sites:
        start = site.file_offset
        end = start + len(site.expected)
        if output[start:end] != site.expected:
            raise PatchError(f"unexpected original bytes at {site.name}")
        if len(site.replacement) != len(site.expected):
            raise AssertionError(f"non-size-preserving hook at {site.name}")
        output[start:end] = site.replacement

    helper_end = PADDING_FILE_OFFSET + len(helper_code)
    output[PADDING_FILE_OFFSET:helper_end] = helper_code

    # Promote the already-present complete final page into the MZ image. The
    # page count stays 0x002C and zero final-page bytes means all 512 bytes of
    # that page are declared. No physical byte is appended.
    struct.pack_into("<H", output, 0x02, 0x0000)

    # Preserve the original executable's whole-file 16-bit word-sum
    # convention while accounting for the header and code changes.
    original_sum = word_sum(data)
    struct.pack_into("<H", output, CHECKSUM_OFFSET, 0)
    checksum = (original_sum - word_sum(output)) & 0xFFFF
    struct.pack_into("<H", output, CHECKSUM_OFFSET, checksum)

    if len(output) != len(data):
        raise PatchError("patch would change the physical executable size")
    if struct.unpack_from("<H", output, 0x02)[0] != 0:
        raise AssertionError("complete-final-page marker was not written")
    if struct.unpack_from("<H", output, 0x04)[0] != 0x002C:
        raise AssertionError("MZ page count changed unexpectedly")
    if word_sum(output) != original_sum:
        raise AssertionError("MZ checksum convention was not preserved")

    allowed = set(range(0x02, 0x04))
    allowed.update(range(CHECKSUM_OFFSET, CHECKSUM_OFFSET + 2))
    for site in sites:
        allowed.update(range(site.file_offset, site.file_offset + len(site.expected)))
    allowed.update(range(PADDING_FILE_OFFSET, PADDING_FILE_OFFSET + PADDING_SIZE))
    changed = {index for index, pair in enumerate(zip(data, output)) if pair[0] != pair[1]}
    unexpected = changed - allowed
    if unexpected:
        raise AssertionError("patch changed bytes outside its ownership map")

    return bytes(output)


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

    if input_path.resolve() == output_path.resolve():
        raise PatchError("input and output must be different files")
    if output_path.exists() and not args.force:
        raise PatchError("output already exists; use --force to replace it")
    if not output_path.parent.is_dir():
        raise PatchError("output directory does not exist")

    original = input_path.read_bytes()
    patched = patch_bytes(original)

    temporary = output_path.with_name(f".{output_path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as stream:
            stream.write(patched)
        os.chmod(temporary, stat.S_IMODE(input_path.stat().st_mode))
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()

    print("EDIT-CPU-05 input validation: passed")
    print("physical size preserved: 0x5800 bytes")
    print("promoted helper range: CS:2AE4..2B49 (102 bytes)")
    print("unused promoted padding: CS:2B4A..2B4F (6 bytes)")
    print(f"patched SHA-256: {hashlib.sha256(patched).hexdigest()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, PatchError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
