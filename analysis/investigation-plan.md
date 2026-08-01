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
| 2. Lightweight static map | Complete; awaiting review | Static architecture and function ledger recorded in `static-map.md` and `function-ledger.csv` |
| 3. Controlled DOSBox-X runs | Ready for review | Correlate small behavioral experiments with code addresses |
| 4. Ghidra analysis | Not started | Recover functions, call relationships, structures, and pseudocode |
| 5. Architecture reconstruction | Not started | Produce an evidence-backed code-design document |

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
- `analysis/static-map.md`
- Annotated disassembly extracts under `analysis/inventory/`

## Phase 3: Controlled DOSBox-X runs

### Tasks

- Verify debugger support in the packaged DOSBox-X build.
- Mount only an isolated writable run directory.
- Capture initial registers, segments, a bounded startup trace, and relevant interrupts.
- Run controlled experiments: immediate exit, idle, one movement input, and one game action.
- Compare traces to isolate action-specific paths.
- If packed, dump expanded memory immediately after transfer to the real entry point.

### Outputs

- DOSBox-X configuration under `analysis/config/`
- Experiment log and trace index
- Bounded traces under `analysis/traces/`
- Runtime dumps under `analysis/dumps/` only when required

## Phase 4: Ghidra analysis

Ghidra is gated on Phase 1 classification. Prefer a pinned Docker-based setup and verify downloaded artefacts. Any required installation remains subject to separate review.

Import according to the classification:

- MZ: `x86:LE:16:Real Mode`
- COM-like: raw 16-bit image at offset `0x100`
- LE/LX or extender: appropriate 32-bit x86 loader
- Unpacked memory: raw image mapped at its observed runtime address

### Outputs

- Reproducible Ghidra setup and project metadata
- Named function and data-symbol ledger
- Call graphs and focused decompiler exports

## Phase 5: Architecture reconstruction

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
