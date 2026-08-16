#!/usr/bin/env python3
"""Decode a bounded ghost-rendering data/CGA capture into a compact report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


DATA_SIZE = 0x2AB0
CGA_SIZE = 0x4000
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def s8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def cga_pixels(cga: bytes) -> set[tuple[int, int]]:
    pixels: set[tuple[int, int]] = set()
    for y in range(200):
        row = (0x2000 if y & 1 else 0) + (y // 2) * 80
        for byte_index, value in enumerate(cga[row : row + 80]):
            if not value:
                continue
            x_base = byte_index * 8
            for bit in range(8):
                if value & (0x80 >> bit):
                    pixels.add((x_base + bit, y))
    return pixels


def sprite_bits(data: bytes, base: int, frame: int) -> list[tuple[int, int]]:
    bits: list[tuple[int, int]] = []
    frame_base = base + frame * 32
    for row in range(16):
        low = data[frame_base + row * 2]
        high = data[frame_base + row * 2 + 1]
        word = (high << 8) | low
        for column in range(16):
            if word & (0x8000 >> column):
                bits.append((column - 8, row - 8))
    return bits


def frame_for_angle(angle: int) -> int:
    return ((angle + 8) & 0xF0) >> 4


def coverage(
    pixels: set[tuple[int, int]], bits: list[tuple[int, int]], x: int, y: int
) -> tuple[int, int, float]:
    present = sum(((x + dx) % 640, (y + dy) % 200) in pixels for dx, dy in bits)
    return present, len(bits), present / len(bits)


def find_ship_candidates(
    data: bytes,
    pixels: set[tuple[int, int]],
    base: int,
    threshold: float = 0.90,
) -> list[dict[str, int | float]]:
    candidates: list[dict[str, int | float]] = []
    for frame in range(16):
        bits = sprite_bits(data, base, frame)
        votes: Counter[tuple[int, int]] = Counter()
        for x, y in pixels:
            for dx, dy in bits:
                votes[((x - dx) % 640, (y - dy) % 200)] += 1
        for (x, y), present in votes.items():
            ratio = present / len(bits)
            if ratio >= threshold:
                candidates.append(
                    {
                        "x": x,
                        "y": y,
                        "frame": frame,
                        "present_bits": present,
                        "sprite_bits": len(bits),
                        "coverage": round(ratio, 6),
                    }
                )
    candidates.sort(
        key=lambda item: (
            -float(item["coverage"]),
            -int(item["present_bits"]),
            int(item["y"]),
            int(item["x"]),
            int(item["frame"]),
        )
    )
    return candidates


def ship_state(data: bytes, slot: int) -> dict[str, object]:
    return {
        "visibility_byte": data[0x0CBC + slot],
        "visibility_bit": data[0x0CBC + slot] & 1,
        "current": {
            "x": u16(data, 0x0D1C + slot),
            "y": u16(data, 0x0D3C + slot),
        },
        "previous_rendered": {
            "x": u16(data, 0x0D5C + slot),
            "y": u16(data, 0x0D7C + slot),
        },
        "dirty": data[0x0E1C + slot],
        "entity_state": s8(data[0x0E3C + slot]),
        "current_angle": data[0x0E5C + slot],
        "previous_angle": data[0x0E7C + slot],
        "previous_frame": frame_for_angle(data[0x0E7C + slot]),
        "action": data[0x0EBC + slot],
        "latch": data[0x0EDC + slot],
        "shield_energy": data[0x0EFC + slot],
        "weapon_energy": data[0x0F1C + slot],
    }


def particle_summary(data: bytes, byte_start: int) -> dict[str, object]:
    positions = [
        {
            "x": u16(data, 0x038D + index),
            "y": u16(data, 0x0441 + index),
        }
        for index in range(byte_start, byte_start + 0x40, 2)
    ]
    return {
        "count": len(positions),
        "first": positions[0],
        "x_range": [min(item["x"] for item in positions), max(item["x"] for item in positions)],
        "y_range": [min(item["y"] for item in positions), max(item["y"] for item in positions)],
        "positions": positions,
    }


def decode(run_id: str) -> dict[str, object]:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run ID must use lowercase letters, digits, dots, underscores, or hyphens")

    run_dir = Path("analysis/dumps/ghost-rendering") / run_id
    data_path = run_dir / "data.bin"
    cga_path = run_dir / "cga.bin"
    data = data_path.read_bytes()
    cga = cga_path.read_bytes()
    if len(data) != DATA_SIZE:
        raise ValueError(f"{data_path} has {len(data)} bytes; expected {DATA_SIZE}")
    if len(cga) != CGA_SIZE:
        raise ValueError(f"{cga_path} has {len(cga)} bytes; expected {CGA_SIZE}")

    pixels = cga_pixels(cga)
    left = ship_state(data, 0x00)
    right = ship_state(data, 0x10)

    logical_checks: dict[str, object] = {}
    for name, state, sprite_base in (
        ("left", left, 0x1340),
        ("right", right, 0x1540),
    ):
        previous = state["previous_rendered"]
        assert isinstance(previous, dict)
        bits = sprite_bits(data, sprite_base, int(state["previous_frame"]))
        present, total, ratio = coverage(
            pixels, bits, int(previous["x"]), int(previous["y"])
        )
        logical_checks[name] = {
            "x": previous["x"],
            "y": previous["y"],
            "frame": state["previous_frame"],
            "present_bits": present,
            "sprite_bits": total,
            "coverage": round(ratio, 6),
        }

    return {
        "run_id": run_id,
        "files": {
            "data": {"path": data_path.as_posix(), "bytes": len(data), "sha256": sha256(data)},
            "cga": {"path": cga_path.as_posix(), "bytes": len(cga), "sha256": sha256(cga)},
        },
        "state": {
            "hyperspace_counters": {"left": data[0x0060], "right": data[0x0061]},
            "players": {"left": left, "right": right},
            "player_mode_bits": data[0x1076],
            "shared_tick": data[0x1080],
            "option_bits": data[0x2040],
            "random_state": list(data[0x2AA0:0x2AA5]),
        },
        "particles": {
            "left": particle_summary(data, 0x00),
            "right": particle_summary(data, 0x40),
        },
        "framebuffer": {
            "lit_pixels": len(pixels),
            "logical_ship_checks": logical_checks,
            "left_ship_candidates": find_ship_candidates(data, pixels, 0x1340),
            "right_ship_candidates": find_ship_candidates(data, pixels, 0x1540),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="capture directory name under analysis/dumps/ghost-rendering")
    parser.add_argument(
        "--write",
        action="store_true",
        help="also write decoded.json inside the ignored capture directory",
    )
    args = parser.parse_args()

    try:
        report = decode(args.run_id)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        output = Path("analysis/dumps/ghost-rendering") / args.run_id / "decoded.json"
        output.write_text(rendered, encoding="utf-8")
        output.chmod(0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
