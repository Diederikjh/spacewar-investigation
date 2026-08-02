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
| 4. Ghidra analysis | In progress | Pinned container validated; executable import and address mapping are next |
| 5. Computer-player behavior | Not started | Explain robot decisions and compare left/right behavior using static and bounded runtime evidence |
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
- [ ] Import the MZ executable as `x86:LE:16:Real Mode` and reproduce the Phase 1/Phase 3 address mappings.
- [ ] Apply the high-confidence function names and subsystem boundaries from `analysis/function-ledger.csv`.
- [ ] Recover the five-byte random-generator state update at runtime offset `28F2` and express its additive/carry recurrence precisely.
- [ ] Recover the BIOS-clock seed path at runtime offset `2916` and determine which state byte, if any, is not overwritten by the seed routine.
- [ ] Explain how the 90-star frontend field initializes positions, calculates signed fixed-point velocities, advances stars, and chooses rendered glyphs.
- [ ] Explain how the 512-pixel gameplay background obtains X/Y coordinates, including masking, rejection ranges, and resulting coordinate distribution.
- [ ] Compare the star consumers with hyperspace, robot, and randomized-sound consumers to distinguish shared generator behavior from caller-specific range mapping.
- [ ] Assess repeatability: identify which initial state and BIOS tick values would reproduce an identical star layout or animation.
- [ ] Identify the exact computer-player decision entry points, action leaves, state inputs, and random-generator calls required by Phase 5.
- [ ] Record the evidence, proposed types, remaining uncertainties, and confidence in `analysis/phase-4-findings.md`.

### Outputs

- Reproducible Ghidra setup and project metadata
- Named function and data-symbol ledger
- Call graphs and focused decompiler exports
- Exact description of random seeding, recurrence, range mapping, and starfield consumers
- Address and data-map handoff for the computer-player investigation

## Phase 5: Computer-player behavior

Phase 5 is gated on the Phase 4 function and data map. The game calls its computer-controlled participants robot players; this phase investigates their decision design without assuming that the left and right implementations are identical.

### Static tasks

- [ ] Trace the F3/F4 frontend options into the left/right robot-mode flags and record the default state.
- [ ] Recover the control-flow split between human and robot handling in the left routine at runtime offset `024F` and the right routine at `04A6`.
- [ ] Identify every state input used by a robot decision: positions, wrapped distances, headings, velocity, energy, weapon/cooldown state, projectile threats, planet/gravity options, tick state, and random values.
- [ ] Recover the decision ordering and conditions for rotation, thrust, phasers, photons, cloak, hyperspace, and energy-management actions.
- [ ] Determine whether decisions are made every foreground iteration, on selected ticks, or through per-action cooldown/latch state.
- [ ] Normalize left slot `00` and right slot `10` accesses, then classify code as shared, mechanically mirrored, or behaviorally different.
- [ ] Compare constants, branch order, target selection, projectile-pool ranges, wraparound calculations, and random-number consumption between left and right.
- [ ] Determine whether any observed asymmetry is intentional policy, data-layout adaptation, update-order bias, or an implementation defect.

### Difficulty sub-question

- [ ] What minimal, explainable code or data modifications could make the computer player more difficult, and how would each modification affect left and right behavior?

For each candidate, record the current behavior, exact decision or constant involved, proposed change, expected gameplay effect, left/right applicability, and risk of unintended behavior. Consider decision cadence, aiming and movement prediction, reaction thresholds, weapon selection, defensive responses, energy management, and reliance on randomness. Rank candidates by likely benefit and implementation risk. Do not modify the original executable; any later proof-of-concept change must be separately reviewed and applied only to an ignored run copy.

### Bounded runtime tasks

- [ ] Use the debugger only for questions that remain ambiguous after Phase 4; do not begin with an unrestricted trace.
- [ ] Run left-robot-only and right-robot-only experiments separately from fresh launches, keeping the other player and frontend options controlled.
- [ ] Break at the confirmed robot decision entry and selected action leaves, stopping after one decision or another explicitly stated small bound.
- [ ] Compare only the required state ranges before and after a decision, normalizing left/right entity indices and projectile pools.
- [ ] If deterministic comparison is required, use the Phase 4 random-state model to establish equivalent seeds and mirrored initial geometry in the ignored guest run copy; record every intentional state change.
- [ ] Use `LOGS` only at a confirmed decision breakpoint with an explicit instruction bound; keep any raw log ignored and summarize only the relevant branch evidence.
- [ ] Validate every indirectly entered debugger command with the cropped-image workflow: verify the input line before Enter, acknowledgement after Enter, and exact breakpoints with `BPLIST` before F5.
- [ ] Treat queued key-release events separately from robot decisions and identify them by scan code when a keyboard breakpoint is unavoidable.

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
