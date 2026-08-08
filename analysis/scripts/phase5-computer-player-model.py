#!/usr/bin/env python3

"""Executable model of the computer-player bearing and decision constants."""

from __future__ import annotations


ANGLE_THRESHOLDS = (
    0x0000,
    0x0324,
    0x064A,
    0x0971,
    0x0C9B,
    0x0FC9,
    0x12FD,
    0x1636,
    0x1976,
    0x1CBE,
    0x2010,
    0x236C,
    0x26D4,
    0x2A49,
    0x2DCC,
    0x3160,
    0x3505,
    0x38BD,
    0x3C8A,
    0x406E,
    0x446A,
    0x4882,
    0x4CB8,
    0x510D,
    0x5586,
    0x5A25,
    0x5EEE,
    0x63E4,
    0x690B,
    0x6E69,
    0x7402,
    0x79DD,
)


def _ratio_bin(smaller: int, larger: int) -> int:
    """Reproduce the 16-bit DIV, SHR, and descending threshold scan."""
    ratio = ((smaller << 16) // larger) >> 1
    for index in range(len(ANGLE_THRESHOLDS) - 1, -1, -1):
        if ratio >= ANGLE_THRESHOLDS[index]:
            return index
    raise AssertionError("the zero threshold must accept every ratio")


def bearing(delta_x: int, delta_y: int) -> int:
    """Return the game's 8-bit bearing for raw target-minus-origin deltas."""
    x_negative = delta_x < 0
    y_negative = delta_y < 0
    absolute_x = abs(delta_x)
    absolute_y = abs(delta_y)

    if absolute_y == absolute_x:
        quadrant_angle = 0x20
    elif absolute_y < absolute_x:
        quadrant_angle = _ratio_bin(absolute_y, absolute_x)
    else:
        quadrant_angle = 0x40 - _ratio_bin(absolute_x, absolute_y)

    angle = 0
    if x_negative:
        angle = 0x80
        quadrant_angle = -quadrant_angle
    if y_negative:
        quadrant_angle = -quadrant_angle
    return (angle + quadrant_angle) & 0xFF


def wrapped_delta(target: int, origin: int, extent: int) -> int:
    """Return a shortest wrapped delta for comparison with the game."""
    raw = target - origin
    return min((raw, raw - extent, raw + extent), key=abs)


def left_detects_threat(delta_x: int, delta_y: int) -> bool:
    """Model the left robot's axis-aligned projectile acceptance square."""
    return abs(delta_x) < 0x60 and abs(delta_y) < 0x60


def right_weapon(random_low_byte: int, delta_x: int, delta_y: int) -> str:
    """Model the right robot's random gate and axis-proximity weapon choice."""
    if not 0 <= random_low_byte <= 0xFF:
        raise ValueError("random low byte must fit in an unsigned byte")
    if random_low_byte >= 0x08:
        return "none"
    close_axes = int(abs(delta_x) < 0x60) + int(abs(delta_y) < 0x60)
    return "phaser" if close_axes == 2 else "photon"


def impulse_enabled(random_low_byte: int) -> bool:
    """Model the shared raw-byte impulse gate."""
    return random_low_byte < 0x10


def hyperspace_requested(random_word: int, mask: int = 0x03FF) -> bool:
    """Model the masked-word hyperspace gate."""
    return (random_word & mask) == 0


def self_test() -> None:
    assert bearing(1, 0) == 0x00
    assert bearing(1, 1) == 0x20
    assert bearing(0, 1) == 0x40
    assert bearing(-1, 1) == 0x60
    assert bearing(-1, 0) == 0x80
    assert bearing(-1, -1) == 0xA0
    assert bearing(0, -1) == 0xC0
    assert bearing(1, -1) == 0xE0

    # Coincident positions take the equality branch and yield 0x20.
    assert bearing(0, 0) == 0x20

    assert left_detects_threat(0x5F, -0x5F)
    assert not left_detects_threat(0x60, 0)
    assert right_weapon(0x07, 0x5F, -0x5F) == "phaser"
    assert right_weapon(0x07, 0x60, 0) == "photon"
    assert right_weapon(0x08, 0, 0) == "none"
    assert impulse_enabled(0x0F)
    assert not impulse_enabled(0x10)
    assert hyperspace_requested(0x0400)
    assert not hyperspace_requested(0x0001)

    # Across the horizontal edge, raw and shortest-wrapped bearings oppose.
    raw_x = 631 - 8
    wrapped_x = wrapped_delta(631, 8, 640)
    assert raw_x == 623
    assert wrapped_x == -17
    assert bearing(raw_x, 0) == 0x00
    assert bearing(wrapped_x, 0) == 0x80
    assert not left_detects_threat(raw_x, 0)
    assert left_detects_threat(wrapped_x, 0)


def main() -> None:
    self_test()
    print("phase5 computer-player model: all assertions passed")
    print("angle convention: 00 right, 40 down, 80 left, C0 up")
    print("edge example: raw delta +623 -> 00; wrapped delta -17 -> 80")


if __name__ == "__main__":
    main()
