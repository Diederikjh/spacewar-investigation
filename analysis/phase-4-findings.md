# Phase 4 Findings: Structured Ghidra Analysis

## Status

Phase 4 is in progress. The approved pinned container is validated, and P4-02 imported the ignored working executable without automatic analysis. The MZ loader, 16-bit real-mode language, memory blocks, relocation addresses, entry point, and Phase 1/3 address conversions all agree. P4-03 is ready to transfer the reviewed static function map before broader automatic analysis.

## Task log

| ID | Task | Evidence boundary | Status |
|---|---|---|---|
| P4-01 | Review the pinned Ghidra container setup | Select and record exact inputs, isolation, mounts, and storage before any download | Complete |
| P4-02 | Import and reproduce address mappings | Confirm the MZ loader, 16-bit real-mode language, entry point, and Phase 1/3 address conversions | Complete |
| P4-03 | Apply the static function map | Transfer high-confidence functions and subsystem boundaries from `analysis/function-ledger.csv` | Ready |
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

The first P4-02 launch exposed one image-construction issue before the container started: the JDK ZIP extractor had not restored Unix execute permissions. The Dockerfile now restores execute permission deterministically only to files identified by their first bytes as scripts or native ELF programs. The cached rebuild and smoke test passed; no additional package or unpinned input was introduced.

## P4-02 import and address mapping

### Preservation and import result

Immediately before import, `analysis/work/Spacewar1985.exe` still matched the SHA-256 in `analysis/manifest.sha256`. The constrained runner mounted that ignored working copy read-only and mounted only the tracked Ghidra scripts plus ignored project, settings, and export directories.

The first successful import deliberately disabled automatic analysis. Ghidra reported:

| Property | Result |
|---|---|
| Loader | Old-style DOS Executable (MZ) |
| Language | `x86:LE:16:Real Mode` |
| Compiler specification | `default` |
| Entry point | `12AB:0000` |
| Relocations | 5 |
| Declared load-module bytes | 21,908 (`0x5594`) |
| Bytes after declared image | 108 (`0x6C`) |

The loader separated the program into these blocks:

| Block | Ghidra range | Size | Interpretation |
|---|---|---:|---|
| `CODE_0` | `1000:0000..1000:2AAF` | `0x2AB0` | Data-first portion of the load module |
| `CODE_1` | `12AB:0000..12AB:2AE3` | `0x2AE4` | Initial code segment through the declared file image |
| `DATA` | `12AB:2AE4..12AB:2AF3` | `0x10` | Minimum uninitialized allocation from the MZ header |
| `HEADER` | `HEADER::00000000..HEADER::000001FF` | `0x200` | File header in a separate, non-memory address space |

`CODE_0` and `CODE_1` total `0x5594` bytes, exactly the declared load-module size. The header block's separate address space explains why a global minimum/maximum-address query does not describe one linear program range.

### Stable address conversions

Ghidra uses `1000` as a conventional base segment and adds the MZ initial `CS` value `02AB` to obtain the canonical code segment `12AB`. Therefore:

```text
file offset = load-module offset + 0x200

load-module 0x0000..0x2AAF:
    Ghidra address = 1000:<load-module offset>

load-module 0x2AB0..0x5593:
    Ghidra address = 12AB:<load-module offset - 0x2AB0>
    runtime CS offset = load-module offset - 0x2AB0
```

At runtime DOS chooses a different load segment. In the Phase 3 run, the initialized load-module base was `01A1`, so adding `02AB` produced the observed code segment `044C`. The segment values can change between launches, while the offsets and conversion above remain stable. Thus Ghidra `12AB:28F2` is the same instruction location as runtime `CS:28F2`, and Ghidra `1000:2AA0` is the random state reached as initialized `DS:2AA0`.

### Reproduced known locations

| Role | Load module | File | Ghidra | Runtime offset |
|---|---:|---:|---:|---:|
| Random state | `2AA0` | `2CA0` | `1000:2AA0` | initialized `DS:2AA0` |
| Program entry | `2AB0` | `2CB0` | `12AB:0000` | `CS:0000` |
| Game entry | `2B6C` | `2D6C` | `12AB:00BC` | `CS:00BC` |
| Frontend entry | `33F0` | `35F0` | `12AB:0940` | `CS:0940` |
| Frontend timer | `41DD` | `43DD` | `12AB:172D` | `CS:172D` |
| Keyboard handler | `4A30` | `4C30` | `12AB:1F80` | `CS:1F80` |
| Game timer | `4DED` | `4FED` | `12AB:233D` | `CS:233D` |
| Next random value | `53A2` | `55A2` | `12AB:28F2` | `CS:28F2` |
| Seed random state | `53C6` | `55C6` | `12AB:2916` | `CS:2916` |
| Background pixels | `53E2` | `55E2` | `12AB:2932` | `CS:2932` |

All ten reported Ghidra locations were checked against eight bytes read independently from the corresponding working-file offset. Nine matched byte-for-byte. At the keyboard handler, file bytes `50 52 57 1E B8 00 00 8E` became `50 52 57 1E B8 00 10 8E` in Ghidra because relocation `12AB:1F85` adjusts the embedded segment word from `0000` to Ghidra's canonical base `1000`. This expected difference independently validates the relocation model. The program entry began `8C D8`, agreeing with the original bytes restored during Phase 3.

Ghidra placed the five relocation records at `12AB:0007`, `12AB:0060`, `12AB:173B`, `12AB:1F85`, and `12AB:2347`. Subtracting the canonical code-segment base reproduces all five Phase 1 relocation offsets.

The ignored raw reports are `analysis/ghidra/exports/p4-02-import-report.txt` and `analysis/ghidra/exports/p4-02-address-report.txt`. They are evidence aids, not publication artefacts.

## Evidence and uncertainty policy

- Use load-module offsets as the stable primary addresses and record Ghidra-space and runtime `CS:` mappings alongside them.
- Treat automatically created functions, signatures, types, and decompiler output as proposals until checked against instructions and control flow.
- Keep exact observed facts separate from inferred intent and attach a confidence level to architectural conclusions.
- Prefer static evidence in Phase 4. Any later debugger experiment must answer one named ambiguity and use the bounded workflow from `analysis/phase-3-findings.md`.
