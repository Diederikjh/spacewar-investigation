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
| Prototype | Applied to an ignored run copy, but one or more validation layers remain |
| Implemented | Applied to an ignored run copy and validated; never implies that the original changed |

## Ledger

| ID | Potential edit | Area | Status | Expected benefit | Main risk | Detailed source |
|---|---|---|---|---|---|---|
| `EDIT-GRAV-01` | More realistic gravity | Physics | Prototype; bounded runtime passed; extended validation pending | Replace the current spring-like field with a force that becomes stronger near the planet and weaker at long distance | Per-tick division cost, near-center behavior, and changed game balance | [Prototype findings](edit-grav-01-findings.md) |
| `EDIT-HYPER-01` | Preserve ship velocity through hyperspace | Physics/gameplay | Proposed; design captured | Retain a ship's incoming momentum when it reappears instead of forcing it to rest | Saved-state placement, immediate post-arrival hazards, and interaction with gravity during absence | [Hyperspace particle cycle](phase-6-findings.md#hyperspace-particle-cycle) |
| `EDIT-HYPER-02` | Reset hyperspace counters at round start | Rendering/lifecycle | Proposed; behavior selected | Prevent an old effect from resuming against newly active ships and stranding XOR sprites | Inserting the reset before initial drawing without disturbing ordinary hyperspace | [Confirmed cause](ghost-rendering-static-audit.md#instrumented-reproduction-and-confirmed-cause) |
| `EDIT-CPU-01` | Increase right weapon attempts | Computer player | Proposed; Phase 5 rank 1 | More frequent offensive weapon decisions through a one-byte threshold change | Faster energy use and more projectile activity | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-02` | Widen left proximity defense | Computer player | Proposed; Phase 5 rank 2 | Let the defensive player engage ships and projectiles from farther away | More distant low-priority phaser use | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-03` | Increase right pursuit thrust | Computer player | Proposed; Phase 5 rank 3 | Close distance more aggressively | Energy drain and overshoot | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-04` | Reduce right random escapes | Computer player | Proposed; Phase 5 rank 4 | Keep the pursuing player in combat more often | Hyperspace may currently provide useful defense | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-05` | Use shortest wrapped deltas | Computer player | Prototype; bounded ship-target behavior passed; extended validation pending | Correct edge-crossing aim and proximity errors | New code space and careful signed wrap arithmetic | [Prototype findings](edit-cpu-05-findings.md) |
| `EDIT-CPU-06` | Add gravity-aware photon-oriented target leading | Computer player | Expanded prototype; startup smoke passed; controlled validation pending | Improve right-player photon aim against moving targets under gravity-off and original-linear-gravity play | Fixed-horizon and gravity approximation, pursuit side effects, raw edge geometry, and shared code-space ownership with `EDIT-CPU-05` | [Prototype findings](edit-cpu-06-findings.md) |
| `EDIT-CPU-07` | Improve left target selection | Computer player | Proposed; Phase 5 rank 7 | Avoid first-slot distractions and make defense more deliberate | Changes the left player's established defensive character | [Difficulty modifications](phase-5-findings.md#difficulty-modifications) |
| `EDIT-CPU-08` | Honour cloak while targeting | Computer player | Investigation pending; design captured | Prevent computer players from seeing a cloaked ship while retaining visible-projectile reactions | Separate left/right policy changes, random-call cadence, and code placement | [Deferred cloak-aware targeting](phase-5-findings.md#deferred-follow-up-cloak-aware-targeting) |
| `EDIT-CPU-09` | Use trouble-aware hyperspace | Computer player/energy | Proposed; design pending | Spend eight weapon-energy units on hyperspace only for a concrete danger or resource crisis | Defining danger without making escape deterministic or exploitable | [Energy-efficiency proposals](#energy-efficiency-proposals) |
| `EDIT-CPU-10` | Fire photons only at high-confidence intercepts | Computer player/energy | Proposed; design pending | Avoid photon energy and slot use when the predicted trajectory is unlikely to hit | Confidence estimation under wrapping, gravity, target actions, and quantized bearings | [Energy-efficiency proposals](#energy-efficiency-proposals) |

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

### Prototype implementation

The size-preserving prototype uses the investigated approximate-radius direction without a table:

1. Take absolute X/Y displacement from the existing center.
2. Approximate radius cheaply, for example `max(abs_x, abs_y) + min(abs_x, abs_y) / 2`.
3. Add a softening radius of `32`.
4. Calculate `scale = floor(262144 / denominator)`.
5. Calculate each component as `floor(abs(component) * scale / denominator)` and restore its direction toward the center.

This retains central symmetry and avoids a square root, but it performs three unsigned divisions per active entity. The 111-byte replacement fits in the 102-byte old routine plus nine adjacent zero bytes, leaving `CS:1E9F` zero before the next routine at `CS:1EA0`. It does not use the trailing padding owned by the separate EDIT-CPU-05 prototype. Exact mapping, bounds, examples, and validation status are recorded in [the prototype findings](edit-grav-01-findings.md).

### Prototype choices and remaining decisions

- The first prototype uses strength `262144` and softening radius `32`; gameplay tuning remains pending.
- Ships and projectiles continue to receive identical acceleration.
- Gravity remains independently selectable when the planet is hidden.
- The existing square planet-collision behavior is unchanged and requires bounded runtime testing with the new field.
- Exhaustive playable-coordinate validation bounds each component at `2048`; the existing absence of a velocity cap is unchanged.
- Establish a cycle budget for up to 16 active entities at approximately 72.8 timer ticks per second.
- Decide whether later tuning is sufficient or whether a table-based approximation warrants a different code-space strategy.

### Validation criteria

1. With gravity disabled, preserve the existing movement-state sequence over an identical bounded tick run.
2. At equal radii in different quadrants, produce symmetric accelerations directed toward `(319, 99)`.
3. Outside the softened center, demonstrate that acceleration magnitude increases as radius decreases.
4. At the center and collision boundary, avoid division errors, overflow, sign reversal, and unstable velocity jumps.
5. Exercise both ships and all fourteen projectile slots without missed timer deadlines or audio disruption.
6. Compare representative trajectories with the current linear field using identical initial state and a bounded tick count.
7. Tune one strength/table revision at a time and record the exact executable mapping and gameplay effect.

## `EDIT-HYPER-01`: preserve ship velocity through hyperspace

### Current behavior

Hyperspace does not merely clear velocity when the ship returns. Its trigger first replaces the ship's four signed 16.16 velocity words with the common particle-cloud drift `(selected destination - previous rendered position) / 64`. The ship is inactive during the effect, so these words drive the shared movement of its 32-pixel slice rather than ordinary ship motion.

When the effect completes, the timer copies the first particle's final coordinate into the ship's current and previous-rendered positions, marks the ship active, and writes zero to its X/Y velocity words. The ship therefore reappears at rest regardless of its momentum before hyperspace.

### Proposed behavior

Save the complete incoming X/Y velocity before the trigger overwrites it, continue using the existing temporary destination drift for the particle animation, and restore the saved velocity when the ship is reactivated:

```text
on hyperspace entry:
    saved_velocity = ship_velocity
    particle_drift = (selected_destination - previous_rendered_position) / 64
    ship_velocity = particle_drift

on hyperspace completion:
    ship_position = first_particle_final_position
    ship_velocity = saved_velocity
```

Preservation means exact signed 16.16 momentum at entry. The first design should not apply thrust, speed limiting, or accumulated gravity while the ship is inactive. Gravity and ordinary motion resume from the restored velocity on the next eligible gameplay timer tick.

### Implementation questions

- Reserve eight bytes per ship for the two low/high velocity pairs without conflicting with simultaneous left/right hyperspace, the title, or the 90-pixel round-end effect.
- Investigate the 26 mutable particle entries unused by the two 32-entry hyperspace slices as possible temporary storage. A round ending during hyperspace may overwrite all 90 entries, but preserved velocity is then irrelevant unless control can return to the same live round.
- Save velocity before either trigger writes its destination drift and restore it at both side-specific completion paths instead of writing zero.
- Keep the existing random destination, 32-pixel animation, landing coordinate, energy cost, duration, and action-latch behavior unchanged.
- Decide whether a post-arrival safety rule is needed when restored momentum immediately crosses a border or enters a collision region. The initial prototype should prefer unchanged normal movement and wrapping rules.
- Re-evaluate code placement against other edits. The saved-state area may be shared data, but trigger and completion hooks still require instructions and explicit ownership.

### Validation criteria

1. Seed positive, negative, mixed-sign, zero, and fractional X/Y velocities and confirm exact bit-for-bit restoration for both ships.
2. Confirm that particle paths, counter boundaries, random-call cadence, selected destination, and final landing coordinate remain identical to an unmodified reference run.
3. Trigger left and right hyperspace simultaneously and prove that their saved velocities and 32-pixel slices do not overlap.
4. Confirm that zero incoming velocity still produces the original at-rest re-entry behavior.
5. Exercise re-entry near every border and near the planet with gravity disabled and enabled; ordinary wrapping, collision, and gravity should resume only after reactivation.
6. Verify computer-player hyperspace uses the same preserved-momentum path without changing its probability, energy, or latch policy.
7. Trigger a round end while one ship is absent and confirm that temporary saved-state reuse cannot leak into the frontend or a later round.
8. Preserve physical EXE size unless a separately reviewed code-space plan explicitly permits expansion.

## `EDIT-HYPER-02`: reset hyperspace counters at round start

### Confirmed defect

The framebuffer and copied entity state are rebuilt for a new round, but the
left/right hyperspace counters at `DS:0060/0061` lie outside the copied range
and are not reset. A full-speed trace caught a new round drawing active ships
with both counters already nonzero. The stale left effect later completed
against a visible active ship, replaced its render coordinates, and stranded
two left-ship XOR images.

### Selected first implementation

Clear both counters at round start, before the initial ships are drawn and
before the gameplay timer can advance an inherited effect:

```text
before new-round initial drawing:
    left_hyperspace_counter = 0
    right_hyperspace_counter = 0
```

The bytes are adjacent at `DS:0060/0061`, so the implementation can treat them
as one zeroed word if instruction placement permits. No particle-array clearing
is required for this fix: game entry already clears the framebuffer, and each
legitimate later particle consumer initializes its own entries before use.

This deliberately fixes the confirmed new-round corruption without changing
F1/frontend presentation or the ordinary same-round hyperspace cycle. Cancelling
effects earlier at frontend or round-end entry remains a separate hardening
option because it has additional visible-particle and shared-array semantics.

### Validation criteria

1. Use the original-binary manual reproduction: enter left or right hyperspace,
   press F1 while particles remain active, start a new round, and prove both
   counters are zero before initial draws.
2. Confirm no completion event can observe an active entity or visible ordinary
   sprite unless a same-round trigger established the matching effect.
3. Preserve normal left/right hyperspace duration, destination, particle
   trajectories, re-entry coordinates, energy cost, and random-call cadence.
4. Exercise immediate and delayed F2 restarts and confirm that menu dwell time
   cannot affect the new-round result.
5. Exercise F2 start, natural round end, F1 return, pause, and
   simultaneous effects with gravity and planet options independently varied.
6. Re-run the circular-trace decoder and require zero initial draws with
   nonzero counters, zero active-entity completions, and zero visibility
   failures over a bounded repeated-relaunch pilot.

## Computer-player difficulty proposals

`EDIT-CPU-01` through `EDIT-CPU-07` are index entries for the ranked candidates already investigated in Phase 5. Their constants, expected effects, left/right applicability, risks, and recommended experiment order remain in [the Phase 5 difficulty table](phase-5-findings.md#difficulty-modifications).

The ranking is an experiment order, not permission to combine edits. The recommended first proof of concept remains `EDIT-CPU-01`, because it is a reversible one-byte change with a directly measurable decision effect. `EDIT-CPU-08` is tracked separately because cloak awareness changes targeting semantics rather than difficulty alone.

### Gravity dependency for `EDIT-CPU-06`

Target leading cannot assume constant straight-line velocity when gravity is enabled. A trajectory predictor must use the active gravity policy: the current linear field documented in [Phase 6](phase-6-findings.md#gravity-calculation), or the softened distance-dependent field if `EDIT-GRAV-01` is implemented. It must also respect the gameplay timer's order of operations: position and wrapping occur before gravity changes velocity for the following tick.

Both the target ship and the fired projectile receive gravity, so predicting only the ship's curved path would still produce an incorrect intercept. A first proof of concept should either be explicitly scoped to gravity-off play or advance target and projectile state through the same bounded fixed-point tick model used by the executable. Any later gravity edit must therefore trigger revalidation of `EDIT-CPU-06` trajectory and intercept tests.

The expanded first prototype is documented in [the EDIT-CPU-06
findings](edit-cpu-06-findings.md). It applies a 64-tick relative-velocity lead
to the right player at photon-like distances. Under the original linear field,
it adds the constant-initial-acceleration term `-delta/4`; this follows from the
64-tick horizon and the field's exact relative acceleration
`-delta/8192`. It is an approximation rather than a discrete simulation, and it
does not model the softened `EDIT-GRAV-01` field. The left policy remains
unchanged because it only fires the instantaneous phaser.

## Energy-efficiency proposals

### `EDIT-CPU-09`: trouble-aware hyperspace

Both computer players currently request hyperspace from a masked random value,
subject to the existing latch and eight-unit weapon-energy charge. A more
energy-efficient policy should treat randomness as a tie-breaker after a danger
test rather than as the reason to leave ordinary play.

Candidate trouble signals include low shield energy, an opposing projectile or
ship inside a bounded threat region, a closing trajectory, imminent planet
contact, or insufficient weapon energy to continue the current policy. The
design must define different left/right thresholds where their defensive and
pursuit roles warrant it, preserve latch behavior, and avoid repeated
hyperspace requests immediately after re-entry.

### `EDIT-CPU-10`: confidence-gated photons

The right computer player currently reaches photon fire through a small random
gate whenever either raw axis is outside phaser range. A confidence gate should
instead require a plausible bounded intercept before spending energy and
occupying a projectile slot. Candidate inputs are predicted miss distance,
intercept time within photon lifetime, bearing-quantization error, wrapped path,
relative velocity, gravity-model validity, and whether the target is
hyperspacing or cloaked.

The first design should retain some randomness only after the confidence test,
so identical situations do not always produce identical fire. Validation should
compare photon attempts, energy spent per hit, slot occupancy, hit rate, round
duration, and left/right win rate over identical bounded seeds. `EDIT-CPU-10`
depends directly on the eventual `EDIT-CPU-05`/`EDIT-CPU-06` combined trajectory
model rather than duplicating a third aiming calculation.
