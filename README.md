# Spacewar1985 Code-Design Investigation

This repository documents an investigation of the 1985 DOS game
`Spacewar1985.exe`. The goal is to explain how the game is structured, how its
major subsystems cooperate, and which carefully scoped gameplay edits appear
feasible.

All six planned investigation phases are complete. The current milestone is a
high-confidence architecture reconstruction plus two size-preserving executable
edit prototypes. The original executable remains immutable and is deliberately
excluded from version control.

## Overall design findings

The executable is a compact, self-contained, predominantly handwritten
16-bit assembly program. Its main design is now understood at the application,
timer, rendering, data, input, computer-player, random, audio, and platform
levels.

| Area | Main finding | Detailed findings |
|---|---|---|
| Platform | A DOS MZ entry layer validates CGA memory, installs keyboard and timer interrupt handlers, configures the PIT and PC speaker, uses a private stack, and restores DOS-visible state on exit. | [Startup and platform lifecycle](analysis/phase-6-findings.md#startup-and-platform-lifecycle) |
| Application states | The game moves between a frontend carousel, live play, pause states, round-end effects, and shutdown. Some timer-driven transitions reset the stack and jump between modes rather than returning through the interrupted call chain. | [Application state model](analysis/phase-6-findings.md#application-state-model) |
| Scheduling | There is no conventional video-frame loop. An unpaced foreground loop handles controls, XOR rendering, collisions, phasers, and transitions, while a roughly 72.8 Hz timer advances motion, resources, cooldowns, hyperspace, planet animation, and audio. | [Execution contexts](analysis/phase-6-findings.md#execution-contexts-and-scheduling), [gameplay architecture](analysis/phase-6-findings.md#gameplay-architecture) |
| Game state | Two ships and fourteen projectile slots are represented by parallel arrays. One even byte index selects the same entity across position, velocity, render, action, energy, lifetime, and state arrays. Motion uses signed split 16.16 fixed-point values. | [Data and memory model](analysis/phase-6-findings.md#data-and-memory-model) |
| Rendering | The game draws directly into monochrome CGA memory. Most pixels and sprites use XOR, allowing the same operation to erase and redraw an object from its previous and current state. | [Rendering](analysis/phase-6-findings.md#rendering) |
| Randomness and effects | A shared five-byte generator drives backgrounds, computer-player choices, sound, hyperspace, and particle effects. Each background makes 512 random pixel-draw attempts. The animated `SPACEWAR` title, hyperspace, and round-end burst reuse 90-entry particle storage in different ways. | [Random-number design](analysis/phase-4-findings.md#p4-04-random-number-design), [title particles and backgrounds](analysis/phase-4-findings.md#p4-05-title-particles-and-backgrounds) |
| Computer players | The left computer player is primarily a proximity defender; the right is a pursuer. They run at foreground speed, use different decision policies, share the human action helpers, do not use shortest wrapped geometry in the original executable, and can see a cloaked opponent. | [Computer-player behavior](analysis/phase-5-findings.md) |
| Gravity | The original field is a linear restoring force toward `(319, 99)`, applied equally to ships and projectiles after position advancement. A separate prototype replaces it with a softened, distance-dependent field. | [Original gravity calculation](analysis/phase-6-findings.md#gravity-calculation), [softened-gravity prototype](analysis/edit-grav-01-findings.md) |

The consolidated architectural account is [Phase 6: Architecture
Reconstruction](analysis/phase-6-findings.md). It is the best starting point for
understanding the game as a whole.

## Investigation progress

| Phase | Focus | Principal result | Findings |
|---|---|---|---|
| 1 | Executable classification | Identified a conventional, unpacked, 22,528-byte DOS MZ executable using 16-bit segmented real mode, embedded resources, direct hardware access, and assembly-oriented layout. | [Phase 1 findings](analysis/phase-1-findings.md) |
| 2 | Static code map | Recovered top-level control flow, interrupt ownership, frontend/gameplay division, parallel entity arrays, fixed-point motion, rendering, input, audio, and random services. | [Phase 2 findings](analysis/phase-2-findings.md) |
| 3 | Controlled runtime investigation | Confirmed the runtime segment, frontend and gameplay timer handlers, Play transition, representative movement and phaser actions, and normal interrupt restoration at exit. | [Phase 3 findings](analysis/phase-3-findings.md) |
| 4 | Structured Ghidra analysis | Established stable address mappings and a high-confidence function map, then recovered the random recurrence, title/background systems, particle reuse, and computer-player handoff. | [Phase 4 findings](analysis/phase-4-findings.md) |
| 5 | Computer-player behavior | Reconstructed left and right decision flows, scheduling, geometry, random gates, policy differences, difficulty candidates, and the scope of cloak-aware targeting. | [Phase 5 findings](analysis/phase-5-findings.md) |
| 6 | Architecture reconstruction | Unified the previous evidence into the application state model, foreground/timer ownership map, subsystem design, hardware dependencies, failure-path audit, and overall code-design assessment. | [Phase 6 findings](analysis/phase-6-findings.md) |

The working checklist and dated progress log remain in the [investigation
plan](analysis/investigation-plan.md). The raw high-confidence function map is
kept in the [function ledger](analysis/function-ledger.csv).

## Executable-edit progress

Executable edits are generated from the exact investigated input by guarded
scripts. Generated executables stay under `analysis/work/` and are excluded from
version control. A prototype status means that the original has not changed and
that further validation may still be required.

| Edit | Purpose | Current status | Findings |
|---|---|---|---|
| `EDIT-CPU-05` | Make both computer players aim and perform proximity checks using the shortest wrapped X/Y deltas. | Size-preserving prototype; static checks, startup, and bounded controlled ship-target behavior passed. Extended behavior validation remains. | [Wrapped-aim findings](analysis/edit-cpu-05-findings.md) |
| `EDIT-GRAV-01` | Replace the original spring-like gravity with a softened field that weakens at long range. | Size-preserving prototype; static checks, exact positive/negative debugger calculations, and bounded CPU-versus-CPU runtime passed. Worst-case timing and extended trajectory validation remain. | [Softened-gravity findings](analysis/edit-grav-01-findings.md) |
| `EDIT-HYPER-01` | Preserve each ship's signed 16.16 velocity across hyperspace instead of restoring it at rest. | Proposed; behavior, storage questions, interactions, and validation criteria are captured, but no executable edit has been made. | [Hyperspace proposal](analysis/potential-edits.md#edit-hyper-01-preserve-ship-velocity-through-hyperspace) |

The [potential edits ledger](analysis/potential-edits.md) is the central index for
these edits and the remaining computer-player difficulty proposals. Shared MZ
validation, code-region ownership, instruction building, checksum preservation,
and output handling live in
[`analysis/scripts/spacewar_edit.py`](analysis/scripts/spacewar_edit.py).

## Reproducing the investigation

The game executable is not included. Place the investigated version at:

```text
artefact/Spacewar1985.exe
```

Its expected SHA-256 hash is:

```text
2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490
```

Run the initial inventory from the repository root with:

```bash
bash analysis/scripts/phase1-inventory.sh
```

The phase findings describe the relevant scripts, bounded runtime procedures,
and reproducible focused exports for later work. General background and the
original high-level approach are in [the DOS investigation
context](docs/dos-game-investigate-context.md).

Runtime traces, memory dumps, emulator logs, local analysis projects, generated
executables, and working copies of the original executable are excluded from
version control.
