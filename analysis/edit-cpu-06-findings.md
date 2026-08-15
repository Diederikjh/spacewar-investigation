# EDIT-CPU-06 Expanded Gravity-Aware Photon-Leading Prototype

## Outcome

`EDIT-CPU-06` now has an expanded prototype patcher. It gives the right
computer player a velocity-based lead at photon-like distances and adds a
relative-acceleration correction when the original linear gravity field is
enabled. Current-position aim is retained at phaser range.

The helper is 124 bytes: it occupies all 108 existing physical padding bytes
and appends one 16-byte paragraph. The physical file grows from `0x5800` to
`0x5810` bytes without moving any existing byte. Static generation, placement,
disassembly, MZ-size, checksum, model, and reproducibility checks pass. A bounded
startup and CPU-versus-CPU smoke test also passes; controlled debugger
calculation and tuning validation remain pending.

This prototype refines the earlier broad proposal to affect both computer
players. The left player fires only the instantaneous phaser, so deliberately
aiming ahead of its selected ship or projectile would reduce accuracy rather
than compensate for weapon travel time. Its policy is therefore unchanged.

## Applying the edit

Run the patcher from the repository root with separate input and output paths:

```bash
analysis/scripts/apply-edit-cpu-06.py \
    artefact/Spacewar1985.exe \
    analysis/work/SPACELEAD.EXE
```

The script accepts only the exact investigated input hash, refuses to overwrite
an existing output unless `--force` is given, refuses the same input and output
path, and aborts unless the helper is exactly 124 bytes and the extension stays
inside the current code segment. Generated executables remain ignored under
`analysis/work/`.

## Prototype behavior

The original right policy computes raw left-minus-right position deltas. The
prototype applies this rule:

```text
current_delta = left_position - right_position

if abs(current_delta_x) < 96
   and abs(current_delta_y) < 96:
    aim_delta = current_delta
else:
    predicted_base = current_delta
    if original_linear_gravity_enabled:
        predicted_base -= floor(current_delta / 4)

    relative_velocity = left_velocity - right_velocity
    aim_delta = predicted_base + floor(relative_velocity * 64)
```

The velocity calculation uses the complete signed 16.16 target and shooter
velocities. Subtracting shooter velocity is necessary because a photon inherits
the firing ship's velocity before its angle-derived launch velocity is added.

The photon initializer adds approximately two pixels per timer tick in the
firing direction. A 64-tick lead horizon therefore represents roughly 128
pixels of nominal projectile travel. It is a named tuning choice, not a solved
intercept time.

For the original gravity field, acceleration is linear in displacement from
the shared center. Subtracting shooter acceleration from target acceleration
cancels the center and gives relative acceleration
`-current_delta / 8192` pixels per tick squared. Applying the elementary
constant-acceleration term `0.5 * acceleration * 64^2` therefore reduces each
current delta by one quarter before velocity leading. The existing bearing
quantizer consumes the result without changing random-call cadence.

Representative component results are:

| Current delta | Target velocity | Shooter velocity | Gravity | Result |
|---:|---:|---:|---:|---:|
| `(+95, +95)` | `(+1, 0)` | `(0, 0)` | Off | `(+95, +95)`; current phaser-range aim |
| `(+96, 0)` | `(+1, 0)` | `(0, 0)` | Off | `(+160, 0)` |
| `(+96, 0)` | `(+0.5, 0)` | `(0, 0)` | Off | `(+128, 0)` |
| `(+96, 0)` | `(-0.5, 0)` | `(0, 0)` | Off | `(+64, 0)` |
| `(+96, 0)` | `(+1, 0)` | `(+1, 0)` | Off | `(+96, 0)`; shared motion cancels |
| `(+96, 0)` | `(+1, 0)` | `(0, 0)` | On | `(+136, 0)`; `+72` gravity base plus `+64` velocity lead |

## Placement and MZ expansion

| Range | Original role | Prototype ownership |
|---|---|---|
| `CS:05E9..05F8` | Load raw right-player X/Y target deltas | Replaced by a near call and thirteen `NOP` bytes |
| `CS:2AE4..2B4F` | 108 physical zero-padding bytes outside the old declared image | First 108 bytes of the lead helper |
| `CS:2B50..2B5F` | Not present in the original physical file | Appended 16-byte continuation |
| `CS:05F9` onward | Existing sign, proximity, bearing, aim, and policy code | Unchanged continuation |

The MZ page count changes from `0x002C` to `0x002D` and the final-page byte field
changes from `0x0194` to `0x0010`, declaring exactly `0x5810` bytes. The loaded
image grows by `0x007C` bytes from its old declared end: 108 bytes were already
physically present and 16 are newly appended. Existing file offsets, code and
data addresses, entry values, and relocation entries do not move.

The shared edit library now provides a guarded same-segment extension path. It
requires extension at the old declared image boundary, recalculates both MZ size
fields and the checksum, rejects growth beyond `CS:FFFF`, verifies every hook
against original bytes, and writes the derived executable atomically.

The helper returns `CX` and `DX` in the form expected at `CS:05F9`, clears `BX`
to its original pre-bearing state, leaves `BP=0` for the existing close-axis
counter, and balances its one-word temporary stack use on every leading path.

## Static validation

- The helper is exactly 124 bytes and ends with `RET` at `CS:2B5F`.
- Disassembly confirms the hook, close-range fallback, gravity-option branch,
  signed one-quarter relative-acceleration correction, signed 16.16 relative
  velocity, exact 64-tick scaling, restored `CX`, cleared `BX`, and return.
- The source is `0x5800` bytes and the output is `0x5810`; the only appended
  range is `CS:2B50..2B5F`, and no original byte moves.
- MZ page count `0x002D` and final-page bytes `0x0010` encode the exact output.
- Changed-byte ownership before the old declared end is limited to the checksum,
  MZ size fields, and 16-byte hook; the replacement tail starts at the old end.
- The original whole-file word-sum convention is preserved.
- Built-in model assertions cover the strict `0x60` boundary, positive,
  negative, fractional, shared-velocity, and gravity-enabled cases.
- Passing an `EDIT-CPU-05` output as input is rejected by the exact-original
  hash guard.
- The generated ignored copy has SHA-256
  `fab0ce14a44cbbd698dcf349facbe373abd7841ee0c1b7a389c26a50a970092d`.

## Compatibility and limitations

This standalone prototype uses the same original padding as `EDIT-CPU-05` and
continues beyond it, so the edits need a new shared placement plan before they
can be combined. It does not occupy the internal gravity region used by
`EDIT-GRAV-01`, but its predictor models the original linear field, not the
softened prototype. Current patchers reject modified inputs rather than compose
incompatible placement or gravity semantics silently.

The helper retains the original raw, non-wrapped geometry. A target crossing a
world edge can still be mis-aimed; a future wrapped-leading design must combine
`EDIT-CPU-05` and this calculation in a larger appended area.

The fixed horizon is not a quadratic intercept solver. It does not vary with
distance, iterate against the chosen bearing, or predict thrust changes,
hyperspace, collisions, or wrapping. The gravity term holds initial relative
acceleration constant; it does not reproduce the timer's discrete
position-before-acceleration sequence over all 64 ticks or the changing
relative gravity caused by the photon's angle-derived movement. It is a small,
inspectable gravity-aware approximation rather than a full trajectory simulator.

The right policy commits aim before its random weapon decision and also uses
that heading for pursuit. Distant no-fire iterations therefore pursue the
predicted point, and a predicted delta entering the close square can affect the
later phaser/photon classification. These are explicit prototype tradeoffs to
inspect dynamically.

## Runtime smoke result

The expanded ignored copy reached the normal animated frontend in the bounded
emulator configuration. Both computer-player options and gravity were enabled,
then one round ran for approximately 15 seconds with both ships and multiple
projectile sprites visible. The round returned normally to the frontend, and F1
completed the ordinary exit path. No visible load, startup, display, option,
live-game, or transition corruption occurred.

This establishes that DOS loads the `0x5810` image and that the expanded helper
can execute during gravity-enabled CPU play without an immediate failure. It is
not an instruction-level validation of the predicted `CX:DX` values and does
not measure hit quality or the intermittent ghost-rendering observation.

## Runtime validation plan

1. Under the debugger, repeat the expanded-image startup and normal-exit check
   while watching for illegal-instruction, stack, and load-boundary faults.
2. With gravity disabled and either current axis at least `0x60`, seed known
   positive, negative, fractional, and shared X/Y velocities; break at
   `CS:05F9` and compare `CX:DX` with the script model.
3. With both current axes below `0x60`, confirm the helper returns the original
   deltas and the right policy retains its ordinary phaser bearing.
4. Enable gravity and confirm the `-delta/4` correction for positive, negative,
   mixed-sign, and fractional relative velocities.
5. Compare right-player photon bearings and hit outcomes for stationary,
   crossing, approaching, receding, and edge-crossing targets over identical
   bounded runs.
6. Run a bounded CPU-versus-CPU stress interval and check pursuit, weapon
   selection, hyperspace, round transitions, and debugger fault output.

## Remaining decisions

1. Tune or replace the 64-tick horizon using measured hit outcomes.
2. Decide whether pursuit should retain current-position aim when no photon is
   requested.
3. Decide whether predicted-close cases should retain current-axis weapon
   classification.
4. Design combined wrapped-leading placement before composing `EDIT-CPU-05`.
5. Compare this approximation with a bounded discrete target-and-projectile
   trajectory model, then design a softened-gravity variant if
   `EDIT-GRAV-01` composition is pursued.
