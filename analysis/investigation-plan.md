# Spacewar1985 Investigation Plan

## Goal

Build an evidence-backed picture of the game's code design: its executable format and runtime, startup sequence, main control loop or state machine, and the boundaries between input, timing, rendering, sound, file handling, and game-state updates.

The investigation aims to recover architectural intent and important data structures. It does not aim to reproduce original source names, comments, or source-file boundaries that are not present in the binary.

## Working rules

- Treat `artefact/Spacewar1985.exe` as the immutable original.
- Run tools and emulators only against `analysis/work/Spacewar1985.exe`.
- Keep bounded traces and record why each trace was taken.
- Do not expose unrelated host directories to the DOS emulator.
- Prefer lightweight native packages; use Docker for heavy tooling where practical.
- Record addresses, observations, and confidence for architectural conclusions.
- Pause at phase gates when a result materially changes the next tool or import choice.
- Keep generated reports repository-relative and free of hostnames or user-specific paths.
- Record only Ubuntu as the analysis platform; do not publish host or installed-software inventories.
- Exclude the original executable, working copies, runtime dumps, traces, and local Ghidra projects from version control.

## Status

| Phase | Status | Outcome |
|---|---|---|
| 1. Preserve and classify | Complete | Conventional unpacked 16-bit MZ; findings recorded in `phase-1-findings.md` |
| 2. Lightweight static map | Complete | Static architecture and function ledger recorded in `phase-2-findings.md` and `function-ledger.csv` |
| 3. Controlled DOS runs | Complete | Runtime entry, mode transitions, input paths, and normal shutdown confirmed in `phase-3-findings.md` |
| 4. Ghidra analysis | Complete | Random, title/background, and computer-player handoff designs recovered in `phase-4-findings.md` |
| 5. Computer-player behavior | Complete | Normalized policies, asymmetries, state ledger, executable model, and ranked difficulty changes recorded in `phase-5-findings.md` |
| 6. Architecture reconstruction | Not started | Produce an evidence-backed code-design document |

## Findings-document convention

Each completed phase has one primary narrative findings document named `analysis/phase-N-findings.md`, where `N` is the phase number. Supporting ledgers, scripts, traces, and inventories remain separate and are linked or referenced from that document.

## Phase 1: Preserve and classify

### Tasks

- [x] Copy the original executable into the isolated working directory.
- [x] Verify that original and working-copy SHA-256 hashes match.
- [x] Record the permitted platform description without host or installed-software details.
- [x] Record file identification and executable metadata.
- [x] Capture the initial bytes and extract strings with offsets.
- [x] Decode the DOS header, including entry and stack addresses.
- [x] Inspect relocations and any secondary executable header.
- [x] Measure whole-file byte entropy and string density.
- [x] Assess compiler/runtime clues and packing likelihood.
- [x] Select the correct Phase 2 analysis branch.

### Classification branches

| Finding | Analysis path |
|---|---|
| Conventional MZ executable | 16-bit segmented real-mode analysis |
| COM-like image | Raw 16-bit image loaded at offset `0x100` |
| LE/LX or DOS extender | 32-bit protected-mode analysis |
| Unpacking or self-modifying stub | Trace transfer to expanded code and capture runtime memory |

### Outputs

- `analysis/manifest.sha256`
- `analysis/inventory/platform.txt`
- `analysis/inventory/file.txt`
- `analysis/inventory/header.hex`
- `analysis/inventory/header-report.txt`
- `analysis/inventory/entry.hex`
- `analysis/inventory/entry-disassembly.txt`
- `analysis/inventory/objdump.txt`
- `analysis/inventory/strings.txt`
- `analysis/inventory/metrics.txt`
- `analysis/inventory/signature-clues.txt`
- `analysis/inventory/trailing-bytes.hex`
- `analysis/phase-1-findings.md`

## Phase 2: Lightweight static map

Proposed native tools: DOSBox-X, radare2, and NASM/ndisasm. Show and review the exact package transaction before installation.

### Tasks

- [x] Cross-check the entry point and memory mappings.
- [x] Disassemble from the entry point and locate startup/runtime boundaries.
- [x] Inventory DOS/BIOS interrupts, port I/O, video-memory references, far calls, indirect calls, and jump tables.
- [x] Create a function ledger with address, proposed name, evidence, and confidence.
- [x] Identify candidates for initialization, shutdown, main loop, input, timing, rendering, sound, random-number generation, entity updates, and collision logic.

### Outputs

- `analysis/function-ledger.csv`
- `analysis/phase-2-findings.md`
- Annotated disassembly extracts under `analysis/inventory/`

## Phase 3: Controlled DOS runs

### Tasks

- [x] Verify debugger support in the packaged DOSBox-X build.
- [x] Mount only an isolated writable run directory.
- [x] Complete a bounded baseline startup and idle run.
- [x] Capture the executable-entry registers and segments.
- [x] Confirm the frontend entry, frontend timer handler, and interrupt vector 8.
- [x] Confirm the F2 Play transition, game entry, and gameplay timer handler.
- [x] Confirm that no additional startup trace is required for the current Phase 3 questions.
- [x] Run the controlled immediate-exit experiment.
- [x] Run one movement input and one game action in separate bounded experiments.
- [x] Compare bounded breakpoint observations to isolate the movement and phaser paths.
- [x] Confirm that no unpacking dump is required because Phase 1 classified the executable as unpacked.

### Outputs

- DOSBox-X configuration under `analysis/config/`
- Primary findings and experiment log in `analysis/phase-3-findings.md`
- Bounded traces under `analysis/traces/`
- Runtime dumps under `analysis/dumps/` only when required

## Phase 4: Ghidra analysis

Ghidra is gated on Phase 1 classification. Prefer a pinned Docker-based setup and verify downloaded artefacts. Any required installation remains subject to separate review.

Import according to the classification:

- MZ: `x86:LE:16:Real Mode`
- COM-like: raw 16-bit image at offset `0x100`
- LE/LX or extender: appropriate 32-bit x86 loader
- Unpacked memory: raw image mapped at its observed runtime address

### Tasks

- [x] Review and approve a pinned Docker-based Ghidra setup before downloading or importing anything.
- [x] Import the MZ executable as `x86:LE:16:Real Mode` and reproduce the Phase 1/Phase 3 address mappings.
- [x] Apply the high-confidence function names and subsystem boundaries from `analysis/function-ledger.csv`.
- [x] Recover the five-byte random-generator state update at runtime offset `28F2` and express its additive/carry recurrence precisely.
- [x] Recover the BIOS-clock seed path at runtime offset `2916` and determine which state byte, if any, is not overwritten by the seed routine.
- [x] Explain how the 90-tile `SPACEWAR` frontend title initializes positions, calculates signed fixed-point velocities, advances particles, and chooses rendered glyphs.
- [x] Explain how the 512-pixel gameplay background obtains X/Y coordinates, including masking, rejection ranges, and resulting coordinate distribution.
- [x] Compare the particle consumers with hyperspace, robot, and randomized-sound consumers to distinguish shared generator behavior from caller-specific range mapping.
- [x] Assess repeatability: identify which initial state and BIOS tick values would reproduce an identical star layout or animation.
- [x] Identify the exact computer-player decision entry points, action leaves, state inputs, and random-generator calls required by Phase 5.
- [x] Record the evidence, proposed types, remaining uncertainties, and confidence in `analysis/phase-4-findings.md`.

### Outputs

- Reproducible Ghidra setup and project metadata
- Named function and data-symbol ledger
- Call graphs and focused decompiler exports
- Exact description of random seeding, recurrence, range mapping, and starfield consumers
- Address and data-map handoff for the computer-player investigation

## Phase 5: Computer-player behavior

Phase 5 is gated on the Phase 4 function and data map. The game calls its computer-controlled participants robot players; this phase investigates their decision design without assuming that the left and right implementations are identical.

### Static tasks

- [x] Trace the F3/F4 frontend options into the left/right robot-mode flags and record the default state.
- [x] Recover the control-flow split between human and robot handling in the left routine at runtime offset `024F` and the right routine at `04A6`.
- [x] Identify every state input used by a robot decision: positions, wrapped distances, headings, velocity, energy, weapon/cooldown state, projectile threats, planet/gravity options, tick state, and random values.
- [x] Recover the decision ordering and conditions for rotation, thrust, phasers, photons, cloak, hyperspace, and energy-management actions.
- [x] Determine whether decisions are made every foreground iteration, on selected ticks, or through per-action cooldown/latch state.
- [x] Normalize left slot `00` and right slot `10` accesses, then classify code as shared, mechanically mirrored, or behaviorally different.
- [x] Compare constants, branch order, target selection, projectile-pool ranges, wraparound calculations, and random-number consumption between left and right.
- [x] Determine whether any observed asymmetry is intentional policy, data-layout adaptation, update-order bias, or an implementation defect.

### Difficulty sub-question

- [x] What minimal, explainable code or data modifications could make the computer player more difficult, and how would each modification affect left and right behavior?

For each candidate, record the current behavior, exact decision or constant involved, proposed change, expected gameplay effect, left/right applicability, and risk of unintended behavior. Consider decision cadence, aiming and movement prediction, reaction thresholds, weapon selection, defensive responses, energy management, and reliance on randomness. Rank candidates by likely benefit and implementation risk. Do not modify the original executable; any later proof-of-concept change must be separately reviewed and applied only to an ignored run copy.

### Bounded runtime tasks

- [x] Apply the debugger gate: static evidence resolved the planned questions, so no unrestricted or bounded trace was run.
- [x] Decide whether separate left-robot-only and right-robot-only runs are required: they are deferred until a gameplay measurement or proof of concept is approved.
- [x] Decide whether decision-entry and action-leaf breakpoints are required: the exact aligned branches and calls were validated statically.
- [x] Decide whether runtime state comparisons are required: the round template, normalized indices, state reads, and writes were validated statically.
- [x] Decide whether deterministic runtime seeding is required: the executable policy model resolves the current geometry question without a run.
- [x] Keep `LOGS` unused because no remaining question justifies an instruction trace.
- [x] Preserve the cropped-image command workflow for any later approved proof-of-concept experiment.
- [x] Avoid keyboard breakpoints and queued key events because Phase 5 required no debugger input.

### Outputs

- `analysis/phase-5-findings.md`
- Updated function/data ledger for computer-player routines and state
- Decision-flow diagram or pseudocode for the normalized robot policy
- Left/right comparison table distinguishing shared logic, mirrored adaptation, and genuine behavioral differences
- Ranked computer-player difficulty modifications with evidence, expected effects, and implementation risks
- Bounded runtime evidence for only the decisions that static analysis could not settle

## Phase 6: Architecture reconstruction

Correlate static and dynamic evidence into an architecture document covering:

- Program startup and runtime initialization.
- Application states and state transitions.
- Per-tick input, game-state, collision, rendering, timing, and audio work.
- Memory model and important global structures or tables.
- Hardware and DOS/BIOS dependencies.
- Unknowns, competing interpretations, and confidence levels.

### Failure-path question

- [ ] Determine whether a reproducible game crash path exists and, if so, recover the minimal ordered series of gameplay, input, interrupt, timing, and state-transition events that causes it.

For each candidate path, record its preconditions, event order, involved routines and shared state, last known valid state, observed failure signature, evidence, and confidence. Distinguish a game defect from a debugger, emulator, or unsupported-hardware failure. Begin with static evidence around interrupt/foreground coordination, non-local mode transitions and stack resets, entity and projectile bounds, resource exhaustion, and option changes. Use a bounded debugger experiment only for a specific remaining hypothesis, keep raw traces and run copies ignored, and do not modify the original executable.

## Post-design follow-up investigations

Begin these only after the Phase 6 architecture document has been captured and reviewed.

### Cloak-aware computer-player targeting

- [ ] Confirm whether projectiles fired by a cloaked ship remain independently visible and targetable; the current recommendation is yes.
- [ ] Evaluate code space in order: in-place reclamation, a proven internal cave, promotion of the existing 108-byte physical padding, then a larger same-segment append.
- [ ] Before promoting the padding, prove the old end-of-image extra allocation is unused and validate the proposed `CS:2AE4..2B4F` ownership range.
- [ ] If the file must grow, keep appended code within the current `CS` where practical and validate the page count, final-page bytes, checksum policy, allocation, hooks, relative branches, and relocations.
- [ ] Make the left robot skip a cloaked right ship at slot `10` while retaining projectile scans at slots `12..1E`.
- [ ] Define and implement the right robot's blind movement, energy, weapon-latch, and random-call behavior.
- [ ] Extend the Phase 5 Ghidra validator and executable policy model before running the modified copy.
- [ ] Apply any proof of concept only to an ignored run copy and verify cloak, decloak, visible-projectile, energy, action, and random-cadence criteria with bounded debugger experiments.
- [ ] Record the final design, patch mapping, runtime evidence, limitations, and whether the estimated 1–2 working-day scope changed because MZ expansion was required.

The investigation boundary, recommended semantics, implementation alternatives, effort estimate, and validation criteria are recorded in `analysis/phase-5-findings.md`.

## Progress log

### 2026-08-01

- Approved the high-level investigation approach.
- Confirmed the workspace contains one 22,528-byte executable and no companion game files.
- Recorded Ubuntu as the analysis platform without publishing host or installed-software details.
- Completed Phase 1 without executing the program or installing software.
- Recorded SHA-256 `2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490`; the original remained unchanged.
- Classified the file as a conventional, unpacked 16-bit MZ executable with no secondary header.
- Found a custom startup that directly initializes CGA memory, the PIT, a keyboard interrupt handler, and its own stack.
- Selected direct 16-bit static disassembly as the Phase 2 path; no unpacking detour is required.
- Changed the inventory generator so published reports contain only repository-relative paths and do not record the host name.
- Added public-repository-safe ignore rules for the executable, working copies, traces, dumps, logs, and Ghidra projects.
- Added `AGENTS.md` to make relative-path and machine-privacy rules persistent for future work.
- Completed the Phase 2 static map without executing the program.
- Identified separate frontend and gameplay timer handlers plus a persistent raw-scan-code keyboard handler.
- Mapped the live game as an interrupt-driven simulation feeding a foreground XOR renderer through dirty state.
- Identified mirrored player/projectile pools implemented as parallel fixed-point state arrays.
- Identified inline display data consumed by return-address manipulation, explaining unreliable linear disassembly boundaries.
- Recorded a Phase 3 breakpoint plan using runtime `CS:` offsets.

### 2026-08-02

- Confirmed the F2 transition from the frontend to game entry and the replacement gameplay timer handler.
- Confirmed that left-player `A` reaches the rotate-counter-clockwise handler at `044C:02B6`.
- Confirmed that left-player `Q` reaches the phaser handler at `044C:0300`.
- Measured the phaser handler changing energy from `7F` to `7E` and its state byte from `FF` to `18` before the follow-up call.
- Kept both input experiments bounded and separate; no unrestricted trace or runtime dump was produced.
- Confirmed that F1 reaches the shutdown path, restores the original timer and keyboard vectors, traverses the PIT-restoration code, and terminates normally.
- Validated debugger commands with narrow screenshot crops; the pre-Enter checkpoint caught incomplete synthetic input before it could affect a run.
- Completed Phase 3 without producing a runtime dump or committing temporary screenshots.
- Added starfield and random-generator reconstruction as an explicit Phase 4 investigation thread.
- Added a dedicated post-Ghidra phase to explain computer-player decisions and compare left/right behavior with bounded, crop-validated debugger experiments where static evidence is insufficient.
- Started Phase 4 by recording a pinned, headless Docker/Ghidra proposal in `analysis/phase-4-findings.md`; no image was downloaded and no executable was imported pending review.
- Built the approved pinned Ghidra container, verified the official release archive against its published SHA-256, and passed the isolated dependency smoke test without mounting the executable.
- Imported the ignored working executable without automatic analysis, confirmed Ghidra's MZ/16-bit real-mode model, and reproduced the Phase 1/Phase 3 address mappings with independent byte checks.
- Transferred all 44 exact high-confidence function-entry proposals into ten namespaced Ghidra subsystem groups while deferring all nine lower-confidence ledger rows.

### 2026-08-07

- Recovered the exact five-byte random recurrence, including the carry fed from the first `ADC` into the second.
- Confirmed the BIOS tick seed mapping, the retained fifth byte, and fresh-launch repeatability conditions.
- Validated all 22 direct calls into the focused random routines and found no additional direct-call candidates.
- Mapped coordinate rejection, background distribution, and the distinct robot, hyperspace, star, and sound interpretations of shared random output.
- Added a deterministic executable model with carry-sensitive and coordinate-rejection assertions.
- Added an architecture-phase task to identify any reproducible crash path and recover its minimal causal event sequence.
- Refined the apparent frontend starfield into a 90-tile `SPACEWAR` title that disperses and exactly reassembles through negated fixed-point velocities.
- Identified a separate 90-pixel round-end effect that reuses the title's mutable arrays and a third unstored 512-pixel background system.
- Completed Phase 4 with a validated computer-player handoff covering mode selection, action tables, state fields, bearing logic, and 28 instruction-aligned robot calls.
- Established that the left robot responds at close range to the opposing ship and its projectiles while the right robot directly pursues the opposing ship, and recorded their different weapon and random-consumption policies for Phase 5.

### 2026-08-08

- Completed Phase 5 with exact normalized pseudocode for the left proximity-defense and right pursuit policies.
- Validated the initial player template, byte-sized angle convention, raw non-wrapped distance behavior, foreground call order, and decision constants.
- Refined the left target scan to include the right ship at slot `10` before projectile slots `12..1E`.
- Recorded shared, mirrored, data-layout-adapted, and genuinely different behaviors in `analysis/phase-5-findings.md`.
- Added a 25-row state ledger and an executable bearing/decision model with deterministic edge-wrap assertions.
- Ranked seven possible difficulty changes without modifying the original executable or an ignored run copy.
- Applied the debugger gate and concluded that a run would not resolve any current static ambiguity.
- Added cloak-aware computer-player targeting as a deferred post-design investigation with separate left/right behavior, code-placement constraints, an effort estimate, and bounded validation criteria.
- Recorded six executable code-space strategies, including the exact 108-byte padding-promotion layout and the larger same-segment capacity available to future implementations.
