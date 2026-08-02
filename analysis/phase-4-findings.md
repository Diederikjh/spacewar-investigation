# Phase 4 Findings: Structured Ghidra Analysis

## Status

Phase 4 is in progress. P4-01 is complete: the approved pinned container was built, the official Ghidra archive matched its published SHA-256, and the dependency smoke test passed under the planned runtime constraints. The executable has not yet been imported; P4-02 is ready to start.

## Task log

| ID | Task | Evidence boundary | Status |
|---|---|---|---|
| P4-01 | Review the pinned Ghidra container setup | Select and record exact inputs, isolation, mounts, and storage before any download | Complete |
| P4-02 | Import and reproduce address mappings | Confirm the MZ loader, 16-bit real-mode language, entry point, and Phase 1/3 address conversions | Ready |
| P4-03 | Apply the static function map | Transfer high-confidence functions and subsystem boundaries from `analysis/function-ledger.csv` | Not started |
| P4-04 | Recover random-number design | Express seeding, the five-byte recurrence, caller range mapping, and repeatability | Not started |
| P4-05 | Recover star and background generation | Explain frontend star initialization/animation and gameplay background placement | Not started |
| P4-06 | Prepare the computer-player handoff | Identify decision entries, action leaves, state inputs, and random-number calls for Phase 5 | Not started |

## P4-01 validated container setup

### Pinned inputs

- Ghidra `12.1.2`, using the official pre-built archive `ghidra_12.1.2_PUBLIC_20260605.zip` from the [official release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.2_build).
- Expected Ghidra archive SHA-256: `b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d`, as published with that release.
- Java 21, matching the [Ghidra 12.1.2 getting-started requirements](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.1.2_build/GhidraDocs/GettingStarted.md#software).
- Docker Official Image `eclipse-temurin:21.0.11_10-jdk-jammy`, pinned to its multi-platform index digest `sha256:9d8dcf999b0bce2453e913823595a5ff2a4e8e9e5d5241b45280d0ff069818ec`.

The Dockerfile downloads only the official Ghidra archive during the image build, validates its SHA-256 before extraction, and fails the build on any mismatch. No third-party Ghidra image or extension is used.

### Initial operating mode

The first pass will use Ghidra's headless analyser. This avoids exposing the host display server to the container and is sufficient for a reproducible import, symbol application, listings, call relationships, and focused decompiler output. If a GUI becomes materially useful, its display-sharing method will be proposed and reviewed separately.

The analysis container will run with:

- networking disabled after the image build;
- a read-only container root filesystem and a temporary `/tmp` filesystem;
- all Linux capabilities dropped and privilege escalation disabled;
- the current user's numeric identity so ignored output is not owned by the container administrator;
- the ignored working executable mounted read-only as `/input/Spacewar1985.exe`;
- only ignored project, home, and export directories under `analysis/ghidra/` mounted read-write;
- no repository-root mount, Docker socket, host devices, emulator data, or display-server socket;
- bounded memory and CPU allocation appropriate to this small executable.

Raw Ghidra projects, caches, listings, and decompiler exports will remain under the already ignored `analysis/ghidra/` tree. Only evidence-backed summaries, selected pseudocode, and symbol/data ledgers intended for publication will be added to tracked files.

### Setup files

- `analysis/docker/ghidra/Dockerfile` — pinned, checksum-verifying image definition.
- `analysis/scripts/phase4-ghidra-build.sh` — image build and identity verification.
- `analysis/scripts/phase4-ghidra-headless.sh` — constrained headless runner using repository-relative source paths.
- A focused Ghidra script under `analysis/ghidra-scripts/` will be added for address, symbol, call, and decompiler exports when the import is confirmed.

### Validation result

The image build resolved the Java base by its recorded digest and downloaded the official Ghidra release archive. The archive matched the expected SHA-256 before extraction. The final image label identified Ghidra `12.1.2`, and the isolated smoke test identified the selected Java `21.0.11` runtime and Ghidra `12.1.2` application version.

The smoke test ran without network access, with a read-only root filesystem, dropped capabilities, disabled privilege escalation, bounded resources, and a temporary `/tmp`. It did not mount the repository or executable. P4-02 will be the first operation to mount the ignored working executable, read-only, into the container.

## Evidence and uncertainty policy

- Use load-module offsets as the stable primary addresses and record Ghidra-space and runtime `CS:` mappings alongside them.
- Treat automatically created functions, signatures, types, and decompiler output as proposals until checked against instructions and control flow.
- Keep exact observed facts separate from inferred intent and attach a confidence level to architectural conclusions.
- Prefer static evidence in Phase 4. Any later debugger experiment must answer one named ambiguity and use the bounded workflow from `analysis/phase-3-findings.md`.
