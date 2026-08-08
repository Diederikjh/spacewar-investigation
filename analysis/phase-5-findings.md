# Phase 5 Findings: Computer-Player Behavior

## Status

Phase 5 is complete. Static instruction review, bounded Ghidra validation, and an executable policy model resolve the mode selection, normalized state, decision order, aiming convention, action cadence, left/right asymmetries, and candidate difficulty changes. No debugger experiment was required because no decision branch remained ambiguous after the static checks.

## Evidence boundary

This phase builds on the Phase 4 address handoff, then checks the exact instructions that establish:

- the round-state template copy and initial player values;
- the left-before-right foreground call order;
- both mode dispatchers and aim commits;
- the strict `0x60` proximity comparisons;
- the impulse, weapon, and hyperspace random constants; and
- the quarter-turn adjustment and shared trigonometric lookup that establish angle orientation.

The ignored report `analysis/ghidra/exports/p5-computer-player-policy-report.txt` contains 18 validated code/data ranges, 22 round-template values, and both foreground control calls. `analysis/ghidra-scripts/ExportComputerPlayerPolicy.java` reproduces those checks. `analysis/scripts/phase5-computer-player-model.py` independently models the bearing, raw-versus-wrapped delta example, proximity tests, and random gates with deterministic assertions.

Two tracked ledgers divide the evidence by purpose:

- `analysis/computer-player-handoff.csv` records decision and action addresses.
- `analysis/computer-player-state.csv` records normalized fields, proposed types, player indexing, initial values, and access evidence.

Phase 5 refined one Phase 4 shorthand. The left scan begins at right-side slot `10`, which is the opposing ship, then continues through projectile slots `12..1E`. It is a proximity-defense scan of all active right-side entities, not a projectile-only scan.

## Normalized state and initial geometry

Game initialization copies `0x360` bytes from the embedded template at `DS:0950` to live state at `DS:0CBC`. The two players occupy byte-indexed slots `00` and `10` across parallel arrays. Seven projectile slots follow each ship at even indices.

| Property | Left slot `00` | Right slot `10` |
|---|---:|---:|
| Initial X | `160` | `480` |
| Initial Y | `46` | `138` |
| Initial angle | `00` (right) | `80` (left) |
| Entity state | `01` (active) | `01` (active) |
| Shield energy | `31` | `31` |
| Weapon energy | `127` | `127` |
| Phaser state | `FF` (ready) | `FF` (ready) |

The robot-mode byte `DS:1076` initially contains zero, so both players default to human control. F3 toggles its left bit and F4 its right bit. Each dispatcher chooses one complete human or robot path; robot control is not layered on top of human key state.

## Scheduling and action timing

The foreground loop calls left controls at `CS:00E4`, processes left rendering and projectiles, then calls right controls at `CS:0158` and processes right rendering and projectiles. An active robot therefore decides once per foreground iteration, not once per timer tick.

The timer and action helpers still constrain the effects:

- Energy transfer helpers act once per invocation only while `(tick & 3) == 0`. Because the foreground can invoke a robot repeatedly while the same timer value remains current, several units may move during one eligible tick window.
- Impulse and cloak consume one weapon-energy unit every 32 timer ticks while enabled.
- A phaser shot spends one weapon-energy unit, changes its signed state from ready `FF` to `18`, and cannot fire again until the timer countdown returns it to a negative ready state.
- A photon uses one of seven side-specific projectile slots, starts that projectile with lifetime/energy `28`, spends one ship weapon-energy unit, and is edge-triggered through a latch.
- Hyperspace is edge-triggered, spends eight weapon-energy units, temporarily removes the ship from normal foreground control, and chooses new bounded coordinates through the shared random generator.

The random gates are evaluated at foreground speed. Under a hypothetical uniform raw output, `AL < 10` would accept 16 of 256 byte values, `AL < 08` would accept eight, and `(AX & 03FF) == 0` would accept one of 1,024 masked values. These ratios are reference fractions, not claims about the shared generator's statistical distribution or independence.

## Angle and distance model

The game represents one turn in one byte:

| Angle | Direction on screen |
|---:|---|
| `00` | Right |
| `40` | Down |
| `80` | Left |
| `C0` | Up |

Both duplicated robot bearing blocks take absolute X and Y deltas, retain quadrant bits, divide the smaller magnitude by the larger, and search the 32-word table at `DS:2250`. This produces 32 quantized steps per quadrant and 256 possible headings. The result is written directly to the ship's byte-sized angle field; the robot does not request gradual rotation. The existing trigonometric component helpers then interpret that angle for thrust and projectiles.

Neither bearing block computes a shortest wrapped delta even though position updates wrap at width `640` and height `200`. The strict proximity checks likewise use raw differences. For example, from X `8` to target X `631`, the game sees `+623` and aims right; the shortest wrapped delta is `-17` and would aim left. The left robot also rejects that entity as distant despite its 17-pixel wrapped separation.

Coincident positions take the equal-axis branch and produce angle `20`. This avoids division by zero but assigns an arbitrary diagonal heading to a zero-length vector.

## Normalized decision flows

### Shared helpers

```text
balance_energy(player):
    if shield > weapon:
        transfer shield -> weapon
    else if shield < weapon:
        transfer weapon -> shield
    # transfer occurs only while tick & 3 == 0

commit_aim(player, target_angle):
    rotation_command = 0
    if angle != target_angle:
        angle = target_angle
        render_dirty |= 1
```

The two balance and commit implementations are duplicated and player-index adapted rather than called through shared routines.

### Left proximity-defense policy

```text
balance_energy(left)

if left.weapon_energy == 0:
    impulse_off(left)
    phaser_release_no_op(left)
    return

target = none
for slot in [right ship 10, projectiles 12, 14, 16, 18, 1A, 1C, 1E]:
    if entity_state(slot) > 0
       and abs(slot.y - left.y) < 0x60
       and abs(slot.x - left.x) < 0x60:
        target = slot
        break

if target exists:
    commit_aim(left, raw_bearing(target.position - left.position))
    try_phaser(left)

impulse = next_random().AL < 0x10
set_impulse(left, impulse)

hyperspace = (next_random().AX & 0x03ff) == 0
set_or_release_hyperspace(left, hyperspace)
```

The opposing ship has first priority whenever it is inside the `191 x 191` strict axis-aligned acceptance square. Otherwise, the first qualifying projectile by allocation-slot order wins; the routine does not select the nearest or fastest projectile. If nothing qualifies, the robot retains its previous angle and still makes random impulse and hyperspace choices. It never requests photon or cloak.

### Right pursuit policy

```text
delta = left.position - right.position       # raw, not wrapped
close_axes = (abs(delta.x) < 0x60) + (abs(delta.y) < 0x60)
commit_aim(right, raw_bearing(delta))

balance_energy(right)

if right.weapon_energy == 0:
    impulse_off(right)
    photon_latch_release(right)
    return

impulse = next_random().AL < 0x10
set_impulse(right, impulse)

weapon_draw = next_random().AL
if weapon_draw >= 0x08:
    photon_latch_release(right)
    phaser_release_no_op(right)
else if close_axes == 2:
    photon_latch_release(right)
    try_phaser(right)
else:
    phaser_release_no_op(right)
    try_photon(right)

hyperspace = (next_random().AX & 0x03ff) == 0
set_or_release_hyperspace(right, hyperspace)
```

The right robot always aims at the left ship and does not check the left entity-state byte. When the weapon gate opens, it chooses phaser only when both raw axis differences are below `0x60`; otherwise it chooses photon. It never requests cloak.

## Left/right design comparison

| Concern | Left | Right | Classification |
|---|---|---|---|
| Mode dispatch | Bit 0, human/robot split | Bit 1, human/robot split | Mechanically mirrored |
| Human action surface | Nine left-key helpers | Nine keypad helpers | Mechanically mirrored |
| Player storage | Slot `00` and projectile slots `02..0E` | Slot `10` and projectile slots `12..1E` | Data-layout adaptation |
| Bearing implementation | Duplicated block | Duplicated block with proximity count | Shared design, mechanically duplicated |
| Distance policy | Raw axis differences | Raw axis differences | Shared omission of wrap correction |
| Target selection | First close right-side entity; ship first | Left ship unconditionally | Genuine policy difference |
| Aim | Direct byte-angle commit | Direct byte-angle commit | Mechanically mirrored |
| Energy management | Balance before target scan | Aim first, then balance | Same policy, reordered work |
| Phaser | Every qualifying close entity, subject to cooldown | Random gate plus two close axes | Genuine policy difference |
| Photon | Never | Random gate when either axis is not close | Genuine policy difference |
| Impulse | One raw random draw | One raw random draw | Shared policy |
| Cloak | Never | Never | Shared policy omission |
| Hyperspace | One masked random draw | One masked random draw | Shared policy |
| Full-decision random use | Two values | Three values | Genuine policy difference |

The executable's `defensive` and `offensive` descriptions align with these policies, but the left robot is not passive: it phasers the right ship whenever that ship is close enough. The asymmetry is too extensive and internally consistent to be a mere indexing accident.

Two smaller biases arise from execution structure:

- Left controls run before right controls. A right photon spawned later in the same foreground pass cannot be considered by the left scan until the next pass.
- When both robots are active and funded, left consumes two shared random values before right consumes three. An early return or hyperspace transition changes the later stream position, so mirrored seeds alone do not create mirrored decisions.

The timer can also interrupt between separate foreground reads of X and Y. The robot does not take an atomic position snapshot, so an update at that boundary can combine coordinates from adjacent timer states. This is a small timing-dependent implementation property, not evidence of a different policy.

## Difficulty modifications

These are investigation candidates only. No executable was modified. Any proof of concept must be separately reviewed and applied only to an ignored run copy.

| Rank | Candidate | Exact current decision | Proposed change | Expected effect | Applies to | Risk |
|---:|---|---|---|---|---|---|
| 1 | Increase right weapon attempts | `CS:06C3` compares `AL` with `08` | Change the immediate to `10` for a first trial | Doubles the accepted raw-byte set from 8 to 16 values, subject to cooldowns, latches, energy, and projectile capacity | Right | Low code risk; faster energy use and more screen activity |
| 2 | Widen left proximity defense | `CS:03D3` and `CS:03E3` compare absolute deltas with `0060` | Change both low immediate bytes to `80` while retaining word comparisons | Lets the left robot engage the ship and projectiles from farther away | Left | Low code risk; may waste phaser cooldown on distant or low-priority entities |
| 3 | Increase right pursuit thrust | `CS:06B3` compares `AL` with `10` | Change the immediate to `20` | Doubles the accepted raw-byte set and should close distance faster because right aim already points at the opponent | Right | Low code risk; higher energy drain and overshoot risk |
| 4 | Reduce right random escapes | `CS:06E7` masks `AX` with `03FF` | Try mask `07FF` | Halves the masked-zero set under a uniform reference, preserving pursuit and eight energy units more often | Right | Low code risk but uncertain gameplay benefit; hyperspace can also be defensive |
| 5 | Use shortest wrapped deltas | Both bearing blocks and their `0x60` proximity tests | Normalize X over `640` and Y over `200` before absolute value and bearing | Removes predictable edge mis-aim and missed close threats | Both | Medium/high implementation risk; needs new code space and careful signed arithmetic |
| 6 | Add target leading | Right targets current ship position; left targets current entity position | Incorporate target velocity and projectile travel time before bearing | Improves shots against moving targets | Both, with different target state | High implementation and tuning risk |
| 7 | Improve left target selection | `CS:03B2` accepts the first close slot | Score proximity or closing velocity, or add an opponent pursuit fallback | Avoids slot-order distractions and makes the left robot a more capable general opponent | Left | High implementation risk and changes its defensive identity |

Rank 1 is the best first experiment: it changes one immediate byte, preserves the existing policy, is independently reversible in an ignored copy, and has an observable outcome. Rank 2 is the clearest left-side counterpart. Combining changes before measuring them would make effects harder to attribute.

The random-threshold candidates scale accepted raw-value sets; their real event rates remain coupled to the generator sequence, foreground speed, timer phase, helper cooldowns, and shared-stream call order. A later proof of concept should therefore compare fixed-duration gameplay outcomes rather than assume the uniform reference fractions are measured probabilities.

## Runtime decision

No Phase 5 debugger session was run. Static evidence settled every planned decision branch, state read, action leaf, call order, and constant. The executable model also demonstrated the wrap discrepancy without mutating runtime memory. A debugger run would currently repeat known control flow rather than resolve an ambiguity.

Runtime work becomes justified if the user approves one concrete modification or asks for a gameplay-level measurement. The smallest useful experiment would then be a fresh right-robot-only comparison at `CS:06C3` and the selected weapon leaf, with a fixed decision bound and the established cropped-input validation workflow.

## Confidence and remaining boundaries

- Confidence is high in the normalized policies, data types, initial values, angle convention, strict proximity geometry, action ordering, and shared-random call order.
- Confidence is high that raw, non-wrapped deltas cause edge mis-aim because the executable model follows the validated instructions and produces opposite raw and wrapped headings in a concrete example.
- Difficulty rankings predict likely gameplay effects from code structure; they are not measurements. The first approved proof of concept should test one candidate at a time.
- No original executable, ignored run copy, or runtime state was changed by Phase 5; raw Ghidra project and report output remain ignored.
