#!/usr/bin/env python3

"""Decode a bounded in-memory ghost-lifecycle trace into a compact report."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct


TRACE_MAGIC = b"GHST"
TRACE_VERSION = 1
TRACE_RECORD_SIZE = 24
TRACE_CAPACITY = 2048
TRACE_HEADER_SIZE = 16
TRACE_DUMP_SIZE = TRACE_HEADER_SIZE + TRACE_RECORD_SIZE * TRACE_CAPACITY
HEADER = struct.Struct("<4sHHHHHBB")
RECORD = struct.Struct("<H12B5H")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

EVENT_NAMES = {
    1: "hyperspace_entry",
    2: "hyperspace_tick",
    3: "hyperspace_completion",
    4: "ship_xor",
    5: "render_snapshot",
}
SIDE_NAMES = {0x00: "left", 0x10: "right"}
INITIAL_POSITIONS = {
    "left": {"x": 160, "y": 46},
    "right": {"x": 480, "y": 138},
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def s8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def parse_record(data: bytes, index: int) -> dict[str, object]:
    values = RECORD.unpack_from(data, TRACE_HEADER_SIZE + index * TRACE_RECORD_SIZE)
    (
        sequence,
        event,
        side,
        tick,
        hyper_left,
        hyper_right,
        visibility,
        dirty,
        entity,
        angle,
        previous_angle,
        action,
        latch,
        flags,
        current_x,
        current_y,
        previous_x,
        previous_y,
    ) = values
    result: dict[str, object] = {
        "buffer_index": index,
        "sequence": sequence,
        "event": EVENT_NAMES.get(event, f"unknown_{event:02x}"),
        "event_id": event,
        "side": SIDE_NAMES.get(side, f"slot_{side:02x}"),
        "slot": side,
        "tick": tick,
        "hyperspace": {"left": hyper_left, "right": hyper_right},
        "visibility": visibility,
        "visibility_bit": visibility & 1,
        "dirty": dirty,
        "entity": s8(entity),
        "angle": angle,
        "previous_angle": previous_angle,
        "action": action,
        "latch": latch,
        "flags": flags,
        "interrupts_enabled": bool(flags & 0x0200),
        "current": {"x": current_x, "y": current_y},
        "previous_rendered": {"x": previous_x, "y": previous_y},
    }
    if event == 4:
        result["xor_operation"] = "erase" if visibility & 1 else "draw"
    return result


def chronological_indices(write_index: int, wrapped: int) -> list[int]:
    if wrapped:
        return list(range(write_index, TRACE_CAPACITY)) + list(range(write_index))
    return list(range(write_index))


def bounded_examples(
    records: list[dict[str, object]], limit: int = 8
) -> list[dict[str, object]]:
    if len(records) <= limit:
        return records
    half = limit // 2
    return records[:half] + records[-half:]


def decode_trace(data: bytes, *, last: int) -> dict[str, object]:
    if len(data) != TRACE_DUMP_SIZE:
        raise ValueError(
            f"trace has {len(data)} bytes; expected {TRACE_DUMP_SIZE} (0x{TRACE_DUMP_SIZE:X})"
        )
    magic, version, record_size, capacity, write_index, next_sequence, wrapped, frozen = HEADER.unpack_from(data)
    if magic != TRACE_MAGIC:
        raise ValueError("trace magic is not GHST")
    if version != TRACE_VERSION:
        raise ValueError(f"unsupported trace version: {version}")
    if record_size != TRACE_RECORD_SIZE or capacity != TRACE_CAPACITY:
        raise ValueError("trace record geometry does not match this decoder")
    if not 0 <= write_index < TRACE_CAPACITY:
        raise ValueError("trace write index is outside the circular buffer")
    if wrapped not in (0, 1) or frozen not in (0, 1):
        raise ValueError("trace header contains an invalid boolean field")
    if last < 0:
        raise ValueError("last-record count must not be negative")

    incomplete: list[int] = []
    records: list[dict[str, object]] = []
    for index in chronological_indices(write_index, wrapped):
        event = data[TRACE_HEADER_SIZE + index * TRACE_RECORD_SIZE + 2]
        if event == 0:
            incomplete.append(index)
            continue
        records.append(parse_record(data, index))

    counts = Counter(f"{item['side']}:{item['event']}" for item in records)
    sequence_gaps: list[dict[str, int]] = []
    for before, after in zip(records, records[1:]):
        expected = (int(before["sequence"]) + 1) & 0xFFFF
        actual = int(after["sequence"])
        if actual != expected:
            sequence_gaps.append({"after": int(before["sequence"]), "expected": expected, "actual": actual})

    completion_visibility = [
        item for item in records
        if item["event_id"] == 3 and int(item["visibility_bit"]) != 0
    ]
    completion_active = [
        item for item in records
        if item["event_id"] == 3 and int(item["entity"]) != 0
    ]
    entry_state = []
    for item in records:
        if item["event_id"] != 1:
            continue
        counter = int(item["hyperspace"][str(item["side"])])
        if counter != 1 or int(item["dirty"]) != 0 or int(item["entity"]) != 0:
            entry_state.append(item)
    snapshot_mismatch = [
        item for item in records
        if item["event_id"] == 5 and item["current"] != item["previous_rendered"]
    ]
    inactive_xor = [
        item for item in records
        if item["event_id"] == 4 and int(item["entity"]) == 0
    ]
    active_hyperspace_tick = [
        item for item in records
        if item["event_id"] == 2 and int(item["entity"]) != 0
    ]
    initial_draw_with_counter = []
    for item in records:
        side = str(item["side"])
        if (
            item["event_id"] == 4
            and item.get("xor_operation") == "draw"
            and int(item["entity"]) != 0
            and item["current"] == INITIAL_POSITIONS.get(side)
            and int(item["hyperspace"][side]) != 0
        ):
            initial_draw_with_counter.append(item)
    unknown_events = [item for item in records if int(item["event_id"]) not in EVENT_NAMES]
    unknown_sides = [item for item in records if int(item["slot"]) not in SIDE_NAMES]

    warnings: list[str] = []
    if incomplete:
        warnings.append("one or more reserved records were not committed before capture")
    if sequence_gaps:
        warnings.append("committed record sequence contains gaps")
    if completion_visibility:
        warnings.append("hyperspace completion observed a nonzero ordinary visibility bit")
    if completion_active:
        warnings.append("hyperspace completion ran while the ship entity was active")
    if entry_state:
        warnings.append("hyperspace entry did not have the expected counter/entity/dirty state")
    if active_hyperspace_tick:
        warnings.append("hyperspace timer movement ran while the ship entity was active")
    if initial_draw_with_counter:
        warnings.append("an initial-position ship draw retained a nonzero hyperspace counter")
    if snapshot_mismatch:
        warnings.append("a completed render snapshot has mismatched current/previous coordinates")
    if unknown_events or unknown_sides:
        warnings.append("trace contains an unknown event or ship slot")

    window = records[-last:] if last else []
    return {
        "header": {
            "version": version,
            "record_size": record_size,
            "capacity": capacity,
            "write_index": write_index,
            "next_sequence": next_sequence,
            "wrapped": bool(wrapped),
            "frozen": bool(frozen),
        },
        "summary": {
            "committed_records": len(records),
            "incomplete_record_indices": incomplete,
            "event_counts": dict(sorted(counts.items())),
            "sequence_gaps": sequence_gaps,
            "completion_visibility_failures": len(completion_visibility),
            "completion_active_entity_failures": len(completion_active),
            "entry_state_failures": len(entry_state),
            "active_hyperspace_tick_failures": len(active_hyperspace_tick),
            "initial_draw_with_counter_failures": len(initial_draw_with_counter),
            "snapshot_coordinate_failures": len(snapshot_mismatch),
            "inactive_ship_xor_events": len(inactive_xor),
            "warnings": warnings,
        },
        "suspicious_records": {
            "completion_visibility": bounded_examples(completion_visibility),
            "completion_active_entity": bounded_examples(completion_active),
            "entry_state": bounded_examples(entry_state),
            "active_hyperspace_tick": bounded_examples(active_hyperspace_tick),
            "initial_draw_with_counter": bounded_examples(initial_draw_with_counter),
            "snapshot_coordinate": bounded_examples(snapshot_mismatch),
        },
        "recent_records": window,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="capture directory name under analysis/dumps/ghost-rendering")
    parser.add_argument("--last", type=int, default=64, help="number of recent committed records to include")
    parser.add_argument("--write", action="store_true", help="write trace-decoded.json in the ignored run directory")
    args = parser.parse_args()

    if not RUN_ID_RE.fullmatch(args.run_id):
        parser.error("run ID must use lowercase letters, digits, dots, underscores, or hyphens")
    trace_path = Path("analysis/dumps/ghost-rendering") / args.run_id / "trace.bin"
    try:
        data = trace_path.read_bytes()
        report = decode_trace(data, last=args.last)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    report["file"] = {
        "path": trace_path.as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        output = trace_path.with_name("trace-decoded.json")
        output.write_text(rendered, encoding="utf-8")
        output.chmod(0o600)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
