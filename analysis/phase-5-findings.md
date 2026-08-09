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

The seven candidates are also indexed as `EDIT-CPU-01` through `EDIT-CPU-07` in the [potential edits ledger](potential-edits.md). This Phase 5 section remains the detailed source for their ranking, constants, expected effects, and risks.

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

## Deferred follow-up: cloak-aware targeting

### Investigation question and status

Static analysis establishes that computer players currently target cloaked ships. Cloak is action-flag bit 1 at `DS:0EBC` for the left ship and `DS:0ECC` for the right ship. It suppresses normal ship rendering but does not hide coordinates or change the positive entity-state byte used by computer-player logic.

This follow-up will investigate and prototype computer-player behavior that honours cloak after the overall architecture design has been captured and reviewed. It is deferred work, not part of the completed Phase 5 implementation, and no executable change has been made.

### Recommended minimal semantics

- A cloaked ship cannot be selected as a target.
- Projectiles fired by a cloaked ship remain visible and targetable.
- A computer player reacquires the ship on the first otherwise eligible foreground iteration after decloaking.
- While its opponent is cloaked, the right robot retains its previous heading, continues energy and non-targeted movement decisions, and does not request phaser or photon fire.
- Preserve the normal number of shared random-generator calls where practical so cloak does not unnecessarily shift random outcomes for other consumers.

The projectile rule should be confirmed before implementation. Treating every projectile as hidden would permit a smaller left-side shortcut, but would make cloak conceal independent visible objects and materially change the recommended behavior.

### Left and right implementation scope

| Side | Current behavior | Required cloak-aware behavior | Relative effort |
|---|---|---|---|
| Left | Scans the right ship at slot `10`, then projectile slots `12..1E` | Test `DS:0ECC & 02`; when set, skip only slot `10` and continue scanning `12..1E` | Lower |
| Right | Always reads the left coordinates and commits aim; when funded, it reaches its weapon gate | Test `DS:0EBC & 02`; when set, skip bearing and weapon selection but execute the approved blind movement/energy policy | Higher |

The recommended right-side blind branch is:

```text
if left is cloaked:
    balance right energy
    retain the previous heading
    make the normal random impulse decision
    consume and discard the normal weapon random draw
    release the photon latch
    make the normal random hyperspace decision
    return
```

The phaser release leaf is a no-op, so no corresponding phaser latch needs clearing. Consuming the discarded weapon draw retains the normal three-value right decision cadence and limits unrelated changes to the shared random stream.

### Code-placement constraint

The cloak test is logically small but does not fit as a one-byte constant modification. Both robot routines are tightly packed, and no safe in-image code cave has yet been validated. Future implementations are nevertheless not limited to same-size instruction replacement: the MZ image can expose its existing physical padding or be extended while retaining all current addresses.

#### Current executable boundary

| Property | Current value |
|---|---:|
| Physical file size | `0x5800` bytes |
| Declared executable size | `0x5794` bytes |
| Header size | `0x0200` bytes |
| Declared load-module size | `0x5594` bytes |
| Code-segment start in load module | `0x2AB0` |
| Current last loaded code byte | `CS:2AE3` |
| Physical zero padding after declared image | `0x006C` bytes (108) |
| Minimum extra allocation | One paragraph (16 bytes) |
| Maximum extra allocation | `0xFFFF` paragraphs |

The 108 padding bytes are physically present but not loaded under the current header. They cannot hold executable code without changing the declared image boundary.

#### Available strategies

| Order | Strategy | Approximate capacity | Main advantage | Main constraint |
|---:|---|---:|---|---|
| 1 | Shorten or replace instructions in place | A few bytes per site | No loader or file-layout change | Fragile and unsuitable for substantial branching |
| 2 | Use a validated internal code cave or unreachable routine | Unknown until audited | Existing addresses and header remain untouched | Space must be proven unreachable and free of inline data or indirect references |
| 3 | Promote the existing physical padding into the MZ image | 108 bytes | No physical file growth; ordinary near control transfers remain available | Requires header and old-extra-allocation audits |
| 4 | Append more code within the current code segment | Up to about `0xD51C` bytes from the present end | Large, contiguous extension without moving current content | File and MZ size fields grow; code must remain at or below `CS:FFFF` |
| 5 | Add another logical code segment | Beyond the near-offset limit | Supports larger isolated additions | Requires far control transfers and possibly new relocation entries |
| 6 | Add an overlay, companion loader, or linkable assembly reconstruction | Flexible | Suitable for extensive future development | Introduces a loader or large reconstruction project |

The strategies are not mutually exclusive. A normal patch uses a three-byte near jump at an existing instruction boundary, executes added code elsewhere, replays any displaced instructions, and jumps back to a reviewed continuation point.

#### Promoting the existing 108 bytes

This is the preferred first option for the cloak-aware proof of concept if no safe internal cave exists. The current MZ header declares 44 pages with `0x0194` bytes used in the last page. The physical file is exactly 44 complete 512-byte pages. Declaring a complete final page would produce:

```text
declared executable size = 0x5800
header size              = 0x0200
load-module size         = 0x5600
new loaded code range    = CS:2AE4..CS:2B4F
```

In conventional MZ encoding, the page count can remain `0x002C` while the final-page byte field changes from `0x0194` to zero, meaning the complete final page is used. The checksum should be regenerated or its treatment explicitly documented even though DOS loaders commonly do not enforce it.

Before using this range, the implementation must prove that the program does not rely on the old minimum-extra-allocation bytes at the current image end as zeroed storage. After expansion, the guaranteed extra paragraph begins after the new image instead. Existing file offsets, relocation sites, entry values, data addresses, code addresses, and the custom stack remain unmoved because content is appended rather than inserted.

Added code in this range can use near jumps and calls within the existing `CS`, and can continue to access current state through `DS`. It should avoid embedding absolute segment constants. If such constants are unavoidable, add and validate the corresponding MZ relocation entries.

The cloak design is likely to fit in 108 bytes: it needs two entry hooks, a left-side slot-skip decision, and a right-side blind-policy branch. Exact assembled size and displaced-instruction handling must be established before treating the capacity as sufficient.

#### Larger same-segment extension

If 108 bytes are insufficient, the physical file can be extended and the MZ page-count and final-page fields recomputed. The current code ends at `CS:2AE3`, leaving `0xD51C` bytes before the 16-bit near-offset boundary at `CS:FFFF`. Staying within this range preserves ordinary near calls and jumps and avoids creating a new code segment.

The implementation must verify:

- the final appended offset remains representable in the current `CS`;
- DOS can allocate the larger image plus its required extra paragraphs;
- no program logic assumes the old image end;
- new code and data have an explicit ownership map;
- hooks begin on decoded instruction boundaries and replay displaced instructions;
- all relative control-flow displacements and any new relocation entries are validated;
- the MZ page count, last-page byte count, checksum policy, and published patch manifest agree; and
- the original executable remains unchanged while all experiments use an ignored run copy.

Only after this capacity is exhausted should another segment, overlay loader, or broader assembly reconstruction be considered. Those approaches materially change control transfers, relocation design, packaging, and regression scope.

### Effort estimate

| Work item | Estimated effort |
|---|---:|
| Confirm final cloak and projectile semantics | 0.5–1 hour |
| Locate and validate code placement; design control transfers | 2–5 hours |
| Implement both computer-player branches on an ignored run copy | 1–3 hours |
| Extend the static validator and executable policy model | 1–2 hours |
| Run bounded DOSBox comparisons and document results | 2–4 hours |
| Expected total with a usable in-image location | Approximately 1–2 working days |

If promoting the existing 108 bytes passes its audits, the work should remain near the lower end of the estimate. Appending beyond the physical file requires broader header, loading, relocation, and regression validation and could take 2–3 working days. A crude right-only early return would be faster but is not recommended because it can freeze behavior, preserve stale action flags, and shift shared random consumption.

### Validation criteria

1. Confirm an uncloaked baseline still aims and fires through the original action leaves.
2. With the left ship cloaked, confirm the right robot does not commit a new bearing or reach phaser/photon action leaves.
3. With the right ship cloaked, confirm the left robot skips slot `10` but can still select an active projectile in slots `12..1E`.
4. Confirm both robots reacquire the opposing ship on the first otherwise eligible decision after decloaking.
5. Confirm energy balance, impulse, hyperspace, cooldown, and photon-latch behavior match the approved blind policy.
6. Compare random-generator call counts between visible and cloaked decisions and document every intentional difference.
7. Keep the original executable unchanged; apply the proof of concept only to an ignored run copy and use bounded debugger breakpoints with the established cropped-input validation workflow.

## Runtime decision

No Phase 5 debugger session was run. Static evidence settled every planned decision branch, state read, action leaf, call order, and constant. The executable model also demonstrated the wrap discrepancy without mutating runtime memory. A debugger run would currently repeat known control flow rather than resolve an ambiguity.

Runtime work becomes justified if the user approves one concrete modification or asks for a gameplay-level measurement. The smallest useful experiment would then be a fresh right-robot-only comparison at `CS:06C3` and the selected weapon leaf, with a fixed decision bound and the established cropped-input validation workflow.

## Confidence and remaining boundaries

- Confidence is high in the normalized policies, data types, initial values, angle convention, strict proximity geometry, action ordering, and shared-random call order.
- Confidence is high that raw, non-wrapped deltas cause edge mis-aim because the executable model follows the validated instructions and produces opposite raw and wrapped headings in a concrete example.
- Difficulty rankings predict likely gameplay effects from code structure; they are not measurements. The first approved proof of concept should test one candidate at a time.
- No original executable, ignored run copy, or runtime state was changed by Phase 5; raw Ghidra project and report output remain ignored.
