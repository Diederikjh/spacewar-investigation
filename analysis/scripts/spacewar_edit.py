#!/usr/bin/env python3

"""Shared, size-preserving edit tools for the investigated executable."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
import stat
import struct
from typing import Callable, Iterable


EXPECTED_SHA256 = "2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490"
EXPECTED_FILE_SIZE = 0x5800
DECLARED_FILE_SIZE = 0x5794
CODE_FILE_BASE = 0x2CB0
PADDING_FILE_OFFSET = 0x5794
PADDING_CS_OFFSET = 0x2AE4
PADDING_SIZE = 0x006C
CHECKSUM_OFFSET = 0x0012


class PatchError(RuntimeError):
    """Raised when an input or layout guard prevents a safe edit."""


class CodeBuilder:
    """Build a compact 8086 block and resolve relative control flow."""

    def __init__(self, base: int) -> None:
        self.base = base
        self.code = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, str]] = []

    def emit(self, *values: int) -> None:
        if any(not 0 <= value <= 0xFF for value in values):
            raise PatchError("machine-code byte is outside 00..FF")
        self.code.extend(values)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise PatchError(f"duplicate code label: {name}")
        self.labels[name] = len(self.code)

    def branch8(self, opcode: int, target: str) -> None:
        self.emit(opcode, 0)
        self.fixups.append((len(self.code) - 1, 1, target))

    def call16(self, target: str) -> None:
        self.relative16(0xE8, target)

    def jump16(self, target: str) -> None:
        self.relative16(0xE9, target)

    def relative16(self, opcode: int, target: str) -> None:
        self.emit(opcode, 0, 0)
        self.fixups.append((len(self.code) - 2, 2, target))

    def finish(self) -> tuple[bytes, dict[str, int]]:
        for operand_at, width, target_name in self.fixups:
            if target_name not in self.labels:
                raise PatchError(f"unknown code label: {target_name}")
            target = self.base + self.labels[target_name]
            next_instruction = self.base + operand_at + width
            displacement = target - next_instruction
            if width == 1:
                if not -0x80 <= displacement <= 0x7F:
                    raise PatchError(f"short branch out of range: {target_name}")
                self.code[operand_at] = displacement & 0xFF
            else:
                if not -0x8000 <= displacement <= 0x7FFF:
                    raise PatchError(f"near control flow out of range: {target_name}")
                struct.pack_into("<h", self.code, operand_at, displacement)
        addresses = {
            name: self.base + offset for name, offset in self.labels.items()
        }
        return bytes(self.code), addresses


@dataclass(frozen=True)
class PatchRegion:
    """One exact, size-preserving byte range owned by an edit."""

    name: str
    file_offset: int
    expected: bytes
    replacement: bytes

    @classmethod
    def at_cs(
        cls,
        name: str,
        cs_offset: int,
        expected: bytes,
        replacement: bytes,
    ) -> "PatchRegion":
        return cls(name, code_file_offset(cs_offset), expected, replacement)

    @property
    def end(self) -> int:
        return self.file_offset + len(self.expected)


def code_file_offset(cs_offset: int) -> int:
    if not 0 <= cs_offset < EXPECTED_FILE_SIZE - CODE_FILE_BASE:
        raise PatchError(f"CS offset is outside the initialized image: {cs_offset:04X}")
    return CODE_FILE_BASE + cs_offset


def near_call(site: int, target: int) -> bytes:
    displacement = target - (site + 3)
    if not -0x8000 <= displacement <= 0x7FFF:
        raise PatchError("hook target is outside 16-bit near-call range")
    return b"\xE8" + struct.pack("<h", displacement)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word_sum(data: bytes | bytearray) -> int:
    if len(data) % 2:
        data = bytes(data) + b"\x00"
    return sum(struct.unpack(f"<{len(data) // 2}H", data)) & 0xFFFF


def validate_original(data: bytes) -> None:
    if sha256_hex(data) != EXPECTED_SHA256:
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


def apply_regions(data: bytes, regions: Iterable[PatchRegion]) -> bytes:
    """Apply guarded regions and preserve size and the original word sum."""

    validate_original(data)
    output = bytearray(data)
    allowed = set(range(CHECKSUM_OFFSET, CHECKSUM_OFFSET + 2))

    for region in regions:
        if len(region.replacement) != len(region.expected):
            raise PatchError(f"non-size-preserving region: {region.name}")
        if not 0 <= region.file_offset <= region.end <= len(output):
            raise PatchError(f"region is outside the physical file: {region.name}")
        owned = set(range(region.file_offset, region.end))
        if allowed.intersection(owned):
            raise PatchError(f"overlapping edit ownership: {region.name}")
        if output[region.file_offset:region.end] != region.expected:
            raise PatchError(f"unexpected original bytes at {region.name}")
        output[region.file_offset:region.end] = region.replacement
        allowed.update(owned)

    original_sum = word_sum(data)
    struct.pack_into("<H", output, CHECKSUM_OFFSET, 0)
    checksum = (original_sum - word_sum(output)) & 0xFFFF
    struct.pack_into("<H", output, CHECKSUM_OFFSET, checksum)

    if len(output) != len(data):
        raise PatchError("edit would change the physical executable size")
    if word_sum(output) != original_sum:
        raise AssertionError("MZ checksum convention was not preserved")

    changed = {
        index
        for index, (before, after) in enumerate(zip(data, output))
        if before != after
    }
    unexpected = changed - allowed
    if unexpected:
        raise AssertionError("edit changed bytes outside its ownership map")
    return bytes(output)


def write_patched_file(
    input_path: Path,
    output_path: Path,
    patched: bytes,
    *,
    force: bool,
) -> None:
    """Atomically write a derived executable while preserving input mode bits."""

    validate_output_path(input_path, output_path, force=force)

    temporary = output_path.with_name(f".{output_path.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as stream:
            stream.write(patched)
        os.chmod(temporary, stat.S_IMODE(input_path.stat().st_mode))
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_output_path(
    input_path: Path,
    output_path: Path,
    *,
    force: bool,
) -> None:
    """Reject unsafe or unavailable output paths before doing edit work."""

    if input_path.resolve() == output_path.resolve():
        raise PatchError("input and output must be different files")
    if output_path.exists() and not force:
        raise PatchError("output already exists; use --force to replace it")
    if not output_path.parent.is_dir():
        raise PatchError("output directory does not exist")


def run_file_edit(
    input_path: Path,
    output_path: Path,
    transform: Callable[[bytes], bytes],
    *,
    force: bool,
) -> bytes:
    """Read an input, apply a byte transform, and atomically write its result."""

    validate_output_path(input_path, output_path, force=force)
    original = input_path.read_bytes()
    patched = transform(original)
    write_patched_file(input_path, output_path, patched, force=force)
    return patched
