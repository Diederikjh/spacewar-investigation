# EDIT-CPU-06 Photon-Leading Prototype

## Outcome

`EDIT-CPU-06` now has a size-preserving prototype patcher. It gives the right
computer player a velocity-based lead at photon-like distances while retaining
current-position aim at phaser range and whenever gravity is enabled.

The helper occupies all 108 existing physical padding bytes after they are
promoted into the declared MZ image. The physical file remains `0x5800` bytes.
Static generation, placement, disassembly, checksum, model, and reproducibility
checks pass. Startup and controlled runtime validation remain pending.

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
path, and aborts unless the emitted helper is exactly 108 bytes. Generated
executables remain ignored under `analysis/work/`.

## Prototype behavior

The original right policy computes raw left-minus-right position deltas. The
prototype begins with those same deltas and applies this rule:

```text
current_delta = left_position - right_position

if gravity_enabled:
    aim_delta = current_delta
else if abs(current_delta_x) < 96
     and abs(current_delta_y) < 96:
    aim_delta = current_delta
else:
    relative_velocity = left_velocity - right_velocity
    aim_delta = current_delta + floor(relative_velocity * 64)
```

The calculation is performed independently for X and Y using the complete
signed 16.16 target and shooter velocities. Subtracting shooter velocity is
necessary because a photon inherits the firing ship's existing velocity before
its angle-derived launch velocity is added.

The photon initializer adds approximately two pixels per timer tick in the
firing direction. A 64-tick lead horizon therefore represents roughly 128
pixels of nominal projectile travel. It is a named tuning choice, not a solved
intercept time. The existing bearing quantizer consumes the resulting signed
deltas without any other policy or random-call change.

Representative component results are:

| Current delta | Target velocity | Shooter velocity | Gravity | Result |
|---:|---:|---:|---:|---:|
| `(+95, +95)` | `(+1, 0)` | `(0, 0)` | Off | `(+95, +95)`; current phaser-range aim |
| `(+96, 0)` | `(+1, 0)` | `(0, 0)` | Off | `(+160, 0)` |
| `(+96, 0)` | `(+0.5, 0)` | `(0, 0)` | Off | `(+128, 0)` |
| `(+96, 0)` | `(-0.5, 0)` | `(0, 0)` | Off | `(+64, 0)` |
| `(+96, 0)` | `(+1, 0)` | `(+1, 0)` | Off | `(+96, 0)`; shared motion cancels |
| `(+96, 0)` | `(+1, 0)` | `(0, 0)` | On | `(+96, 0)`; current-position fallback |

## Placement and ownership

| Range | Original role | Prototype ownership |
|---|---|---|
| `CS:05E9..05F8` | Load raw right-player X/Y target deltas | Replaced by a near call and thirteen `NOP` bytes |
| `CS:2AE4..2B4F` | 108 physical zero-padding bytes outside the original declared image | Promoted right-player lead helper |
| `CS:05F9` onward | Existing sign, proximity, bearing, aim, and policy code | Unchanged continuation |

The MZ page count remains `0x002C`; the final-page byte field changes from
`0x0194` to zero so the already-present complete final page is loaded. Existing
file offsets, code addresses, data addresses, entry values, and relocation
entries do not move.

The helper returns `CX` and `DX` in the form expected at `CS:05F9`, clears `BX`
to its original pre-bearing state, leaves `BP=0` for the existing close-axis
counter, and balances its one-word temporary stack use on every leading path.

## Static validation

- The emitted helper is exactly 108 bytes and ends with `RET` at `CS:2B4F`.
- Disassembly confirms the near call, both fallback branches, signed 16.16
  relative-velocity subtraction, exact 64-tick component scaling, restored
  `CX`, cleared `BX`, and return to the original bearing block.
- The source and output are both `0x5800` bytes; no byte is appended, inserted,
  or removed.
- Changed-byte ownership is limited to the checksum word, final-page MZ field,
  16-byte hook, and promoted helper region.
- The original whole-file word-sum convention is preserved.
- Built-in model assertions cover the strict `0x60` boundary, positive,
  negative, fractional, shared-velocity, and gravity-enabled cases.
- A second generation was byte-for-byte identical.
- Passing an `EDIT-CPU-05` output as input is rejected by the exact-original
  hash guard.
- The generated ignored copy has SHA-256
  `f7a1c68f63346fbda408c31600412414ad946573f12320154e6aba366879040e`.

## Compatibility and limitations

This is a standalone prototype generated from the original executable. It uses
the same 108-byte region as `EDIT-CPU-05`, so those two edits cannot be combined
without a new shared code-placement plan. It does not use the internal gravity
region occupied by `EDIT-GRAV-01`, but current patchers intentionally reject
already modified input rather than compose edits silently.

The helper deliberately retains the original raw, non-wrapped geometry. A
target crossing a world edge can therefore still be mis-aimed; a future combined
wrapped-leading design must consolidate `EDIT-CPU-05` and this calculation in a
larger placement area.

The fixed 64-tick horizon is not a quadratic intercept solver. It does not vary
with distance, iterate against the chosen bearing, or predict thrust changes,
hyperspace, collisions, or acceleration. Leading is disabled under gravity
because both target and projectile trajectories would otherwise need to be
advanced through the active gravity model.

The existing policy commits aim before its random weapon decision and also uses
that heading for pursuit. Consequently, distant no-fire iterations pursue the
predicted point, and a predicted delta that enters the close square can affect
the later phaser/photon classification. These are explicit prototype tradeoffs
to inspect dynamically, not claims of a complete intercept policy.

## Runtime validation plan

1. Confirm that the promoted image reaches the normal animated frontend without
   an illegal-instruction or stack failure.
2. With gravity disabled and either current axis at least `0x60`, seed known
   positive, negative, fractional, and shared X/Y velocities; break at
   `CS:05F9` and compare `CX:DX` with the script model.
3. With both current axes below `0x60`, confirm the helper returns the original
   deltas and the right policy retains its ordinary phaser bearing.
4. Enable gravity and confirm the same current-position fallback before testing
   the unmodified gravity-enabled game path.
5. Compare right-player photon bearings and hit outcomes for stationary,
   crossing, approaching, receding, and edge-crossing targets over identical
   bounded runs.
6. Run a bounded CPU-versus-CPU stress interval and check pursuit, phaser/photon
   selection, hyperspace, round transitions, and debugger fault output.

## Remaining decisions

1. Decide whether 64 ticks is an enjoyable lead horizon or should become a
   smaller, larger, or distance-banded constant.
2. Decide whether pursuit should retain current-position aim when no photon is
   requested.
3. Decide whether predicted-close cases should retain the original current-axis
   weapon classification.
4. Design a combined wrapped-leading implementation before attempting to use
   `EDIT-CPU-05` and `EDIT-CPU-06` together.
5. Revisit gravity-aware interception only with a bounded target-and-projectile
   trajectory model for the selected gravity implementation.
