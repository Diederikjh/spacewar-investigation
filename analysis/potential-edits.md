# Potential Edits Ledger

## Purpose

This ledger indexes possible future changes discovered during the code-design investigation. An entry is a proposal, not approval to modify the executable. Each edit requires its own design review, ignored run copy, validation plan, and explicit approval before implementation.

The original executable remains immutable. Detailed investigation findings remain authoritative; this document links to them instead of duplicating their full evidence.

## Status terms

| Status | Meaning |
|---|---|
| Proposed | An evidence-backed idea exists, but implementation has not been approved |
| Design pending | Important semantics or implementation choices remain open |
| Investigation pending | More evidence is required before implementation design |
| Implemented | Applied to an ignored run copy and validated; never implies that the original changed |

## Ledger

| ID | Potential edit | Area | Status | Expected benefit | Main risk | Detailed source |
|---|---|---|---|---|---|---|
| `EDIT-GRAV-01` | More realistic gravity | Physics | Proposed; design pending | Replace the current spring-like field with a force that becomes stronger near the planet and weaker at long distance | Per-tick cost, near-center instability, fixed-point overflow, code space, and changed game balance | [Current gravity calculation](phase-6-findings.md#gravity-calculation) |
| `EDIT-CPU-01` | Increase right weapon attempts | Computer player | Proposed; Phase 5 rank 1 | More frequent offensive weapon decisions through a one-byte threshold change | Faster energy use and more projectile activity | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-02` | Widen left proximity defense | Computer player | Proposed; Phase 5 rank 2 | Let the defensive player engage ships and projectiles from farther away | More distant low-priority phaser use | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-03` | Increase right pursuit thrust | Computer player | Proposed; Phase 5 rank 3 | Close distance more aggressively | Energy drain and overshoot | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-04` | Reduce right random escapes | Computer player | Proposed; Phase 5 rank 4 | Keep the pursuing player in combat more often | Hyperspace may currently provide useful defense | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-05` | Use shortest wrapped deltas | Computer player | Proposed; Phase 5 rank 5 | Correct edge-crossing aim and proximity errors | New code space and careful signed wrap arithmetic | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-06` | Add target leading | Computer player | Proposed; Phase 5 rank 6 | Improve attacks against moving targets | High implementation and tuning complexity; trajectory prediction must follow the active gravity model | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-07` | Improve left target selection | Computer player | Proposed; Phase 5 rank 7 | Avoid first-slot distractions and make defense more deliberate | Changes the left player's established defensive character | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-08` | Honour cloak while targeting | Computer player | Investigation pending; design captured | Prevent computer players from seeing a cloaked ship while retaining visible-projectile reactions | Separate left/right policy changes, random-call cadence, and code placement | [Deferred cloak-aware targeting](phase-5-findings.md#deferred-follow-up-cloak-aware-targeting) |

## `EDIT-GRAV-01`: more realistic gravity

### Current behavior

The current routine at `CS:1E30` applies the same linear restoring acceleration to every active ship and projectile:

```text
acceleration_x = -8 * (x - 319)
acceleration_y = -8 * (y - 99)
```

This is computationally inexpensive, but it behaves like a spring: acceleration grows with distance from the planet. A more familiar gravitational field would become stronger as distance decreases.

### Proposed behavior

Use a softened inverse-square central field around `(319, 99)`. In design notation:

```text
to_planet_x = 319 - x
to_planet_y =  99 - y
radius_squared = to_planet_x^2 + to_planet_y^2

acceleration = gravity_strength * to_planet
             / (radius_squared + softening^2)^(3/2)
```

The softening term prevents a singularity and unbounded acceleration at the planet center. The formula describes the desired behavior, not a requirement to calculate a square root or division directly on every timer tick.

### Likely implementation direction

The practical 16-bit design should investigate a distance-banded or lookup-table approximation:

1. Take absolute X/Y displacement from the existing center.
2. Approximate radius cheaply, for example `max(abs_x, abs_y) + min(abs_x, abs_y) / 2`.
3. Quantize that radius into a bounded table index.
4. Look up a softened distance-dependent scale.
5. Apply the scale with reviewed fixed-point shifts to the signed X/Y direction.

This retains central symmetry while avoiding a per-entity square root and general division. Exact table values, fixed-point format, code placement, and cycle cost remain design questions. Replacing the current approximately 102-byte gravity routine and helper in place may be possible only for a very compact approximation; otherwise the executable-space strategies in [Phase 5](phase-5-findings.md#code-placement-constraint) apply.

### Decisions required before implementation

- Choose the desired gravity strength and softening radius.
- Decide whether ships and projectiles continue to receive identical acceleration.
- Decide whether gravity remains independently selectable when the planet is hidden.
- Decide how the field interacts with the existing square planet-collision region.
- Set maximum acceleration and velocity policies that cannot overflow the signed 16.16 state.
- Establish a cycle budget for up to 16 active entities at approximately 72.8 timer ticks per second.
- Select code and table placement without assuming that physical file padding is currently loaded.

### Validation criteria

1. With gravity disabled, preserve the existing movement-state sequence over an identical bounded tick run.
2. At equal radii in different quadrants, produce symmetric accelerations directed toward `(319, 99)`.
3. Outside the softened center, demonstrate that acceleration magnitude increases as radius decreases.
4. At the center and collision boundary, avoid division errors, overflow, sign reversal, and unstable velocity jumps.
5. Exercise both ships and all fourteen projectile slots without missed timer deadlines or audio disruption.
6. Compare representative trajectories with the current linear field using identical initial state and a bounded tick count.
7. Tune one strength/table revision at a time and record the exact executable mapping and gameplay effect.

## Computer-player difficulty proposals

`EDIT-CPU-01` through `EDIT-CPU-07` are index entries for the ranked candidates already investigated in Phase 5. Their constants, expected effects, left/right applicability, risks, and recommended experiment order remain in [the Phase 5 difficulty table](phase-5-findings.md#difficulty-modifications).

The ranking is an experiment order, not permission to combine edits. The recommended first proof of concept remains `EDIT-CPU-01`, because it is a reversible one-byte change with a directly measurable decision effect. `EDIT-CPU-08` is tracked separately because cloak awareness changes targeting semantics rather than difficulty alone.

### Gravity dependency for `EDIT-CPU-06`

Target leading cannot assume constant straight-line velocity when gravity is enabled. A trajectory predictor must use the active gravity policy: the current linear field documented in [Phase 6](phase-6-findings.md#gravity-calculation), or the softened distance-dependent field if `EDIT-GRAV-01` is implemented. It must also respect the gameplay timer's order of operations: position and wrapping occur before gravity changes velocity for the following tick.

Both the target ship and the fired projectile receive gravity, so predicting only the ship's curved path would still produce an incorrect intercept. A first proof of concept should either be explicitly scoped to gravity-off play or advance target and projectile state through the same bounded fixed-point tick model used by the executable. Any later gravity edit must therefore trigger revalidation of `EDIT-CPU-06` trajectory and intercept tests.
