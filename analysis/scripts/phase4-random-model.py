#!/usr/bin/env python3

"""Executable model of the five-byte random state used by the game."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    state: tuple[int, int, int, int, int]
    value: int


def seed_state(
    bios_ticks: int,
    retained_byte: int = 0,
) -> tuple[int, int, int, int, int]:
    """Model CS:2916: copy the BIOS tick dword and retain state byte five."""
    if not 0 <= bios_ticks <= 0xFFFFFFFF:
        raise ValueError("BIOS ticks must fit in an unsigned 32-bit value")
    if not 0 <= retained_byte <= 0xFF:
        raise ValueError("retained byte must fit in an unsigned byte")

    return (
        bios_ticks & 0xFF,
        (bios_ticks >> 8) & 0xFF,
        (bios_ticks >> 16) & 0xFF,
        (bios_ticks >> 24) & 0xFF,
        retained_byte,
    )


def next_random(state: tuple[int, int, int, int, int]) -> Step:
    """Model CS:28F2, preserving both ADC carry stages exactly."""
    if len(state) != 5 or any(not 0 <= byte <= 0xFF for byte in state):
        raise ValueError("state must contain exactly five unsigned bytes")

    first_sum = state[0] + state[3] + 1
    first_carry = int(first_sum > 0xFF)
    new_byte = ((first_sum & 0xFF) + state[4] + first_carry) & 0xFF
    next_state = (new_byte, state[0], state[1], state[2], state[3])

    # The routine returns the previous leading byte in AH and the new byte in AL.
    return Step(next_state, (state[0] << 8) | new_byte)


def accepted_coordinate(
    state: tuple[int, int, int, int, int],
    mask: int,
    lower: int,
    upper: int,
) -> tuple[tuple[int, int, int, int, int], int, int]:
    """Apply the coordinate caller's mask and half-open rejection interval."""
    calls = 0
    while True:
        step = next_random(state)
        state = step.state
        calls += 1
        candidate = step.value & mask
        if lower <= candidate < upper:
            return state, candidate, calls


def format_state(state: tuple[int, int, int, int, int]) -> str:
    return " ".join(f"{byte:02X}" for byte in state)


def self_test() -> None:
    assert seed_state(0x12345678) == (0x78, 0x56, 0x34, 0x12, 0x00)

    step = next_random((0x78, 0x56, 0x34, 0x12, 0x00))
    assert step == Step((0x8B, 0x78, 0x56, 0x34, 0x12), 0x788B)

    step = next_random(step.state)
    assert step == Step((0xD2, 0x8B, 0x78, 0x56, 0x34), 0x8BD2)

    # This vector distinguishes the two chained ADC operations from one sum.
    step = next_random((0xFF, 0x00, 0x00, 0xFF, 0x00))
    assert step == Step((0x00, 0xFF, 0x00, 0x00, 0xFF), 0xFF00)

    state = seed_state(0x12345678)
    state, x_coordinate, x_calls = accepted_coordinate(
        state, 0x03FF, 8, 0x278)
    state, y_coordinate, y_calls = accepted_coordinate(
        state, 0x01FF, 8, 0x0C0)
    assert (x_coordinate, x_calls) == (0x08B, 1)
    assert (y_coordinate, y_calls) == (0x05E, 2)


def main() -> None:
    self_test()

    state = seed_state(0x12345678)
    print(f"seed state: {format_state(state)}")
    for index in range(1, 9):
        step = next_random(state)
        state = step.state
        print(
            f"step {index}: value={step.value:04X} "
            f"state={format_state(state)}"
        )


if __name__ == "__main__":
    main()
