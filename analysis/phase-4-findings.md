# Phase 4 Findings: Structured Ghidra Analysis

## Status

Phase 4 is in progress. The approved pinned container and P4-02 address model are validated. P4-03 transferred all exact high-confidence function-entry proposals into namespaced subsystem groups without automatic disassembly or function creation. P4-04 recovered the random-generator design; star and background generation are next.

## Task log

| ID | Task | Evidence boundary | Status |
|---|---|---|---|
| P4-01 | Review the pinned Ghidra container setup | Select and record exact inputs, isolation, mounts, and storage before any download | Complete |
| P4-02 | Import and reproduce address mappings | Confirm the MZ loader, 16-bit real-mode language, entry point, and Phase 1/3 address conversions | Complete |
| P4-03 | Apply the static function map | Transfer high-confidence functions and subsystem boundaries from `analysis/function-ledger.csv` | Complete |
| P4-04 | Recover random-number design | Express seeding, the five-byte recurrence, caller range mapping, and repeatability | Complete |
| P4-05 | Recover star and background generation | Explain frontend star initialization/animation and gameplay background placement | Ready |
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

## P4-03 high-confidence function map

The tracked function ledger contains 53 proposed entries: 44 `high`, eight `medium-high`, and one `medium`. P4-03 applied only the 44 exact `high` rows. The remaining nine rows were intentionally deferred rather than silently promoted.

Each applied name is a user-defined label nested beneath two explicit namespaces:

```text
investigation::<subsystem>::<proposed-name>
```

For example, runtime `CS:28F2` is now labelled `investigation::math::next_random` at Ghidra `12AB:28F2`. The ten subsystem namespaces are `audio`, `control`, `frontend`, `gameplay`, `input`, `interrupts`, `math`, `platform`, `rendering`, and `state`.

Every label has a plate comment containing the ledger's subsystem, exact confidence, and evidence. The `investigation` namespace and comment wording make clear that these are evidence-backed proposals, not recovered original symbols.

This task did not run automatic analysis, disassemble instructions, or create Ghidra function objects. Keeping the entries as primary labels lets later focused disassembly adopt the reviewed names while avoiding premature flow-following through inline display data. The transfer script validated every relationship:

```text
load-module offset = 0x2AB0 + runtime CS offset
Ghidra address      = 12AB:<runtime CS offset>
```

The ignored report `analysis/ghidra/exports/p4-03-ledger-report.txt` matches all 44 applied source rows exactly, confirms that each label is primary, confirms that no function object was created, and records nine deferred lower-confidence rows.

## P4-04 random-number design

### Evidence boundary

The focused Ghidra export covered only the five routines at runtime `CS:28D0..2948`, the six storage bytes at initialized `DS:2AA0..2AA5`, and reviewed direct call sites. It validated 22 near-call opcodes and their relative targets. A byte-level sweep found exactly the same 22 direct-call candidates into the five focused routines, so the reviewed direct-call list is complete.

The ignored raw report is `analysis/ghidra/exports/p4-04-random-report.txt`. The tracked `analysis/ghidra-scripts/ExportRandomDesign.java` reproduces its bounded byte and call checks. No automatic analysis, function creation, decompiler inference, or debugger run was needed.

### Five-byte state and recurrence

The active state is five bytes at initialized `DS:2AA1..2AA5`. The preceding byte at `DS:2AA0` is scratch space for the newly calculated byte. Let the pre-call active state be `(q0, q1, q2, q3, q4)`, in ascending address order.

```text
first = q0 + q3 + 1
carry = 1 if first exceeds 0xFF, otherwise 0
new   = ((first & 0xFF) + q4 + carry) & 0xFF

state' = (new, q0, q1, q2, q3)
AX     = (q0 << 8) | new
```

The initial `+1` comes from `STC` before the first `ADC`. The carry from that addition is then consumed by the second `ADC`; its final carry is discarded. This is not always equivalent to adding `q0 + q3 + q4 + 1` modulo 256. For example, state `FF 00 00 FF 00` produces new byte `00`, return value `FF00`, and next state `00 FF 00 00 FF`.

The copy loop first writes the calculated byte to scratch `2AA0`, then copies `2AA4..2AA0` upward into `2AA5..2AA1`. On return, `AL` still contains the new byte and `AH` is reloaded from `2AA2`, which now contains the previous `q0`.

The executable model in `analysis/scripts/phase4-random-model.py` preserves both carry stages and contains deterministic assertions. With BIOS tick value `0x12345678` and the retained byte zero, its first results are:

| Step | Returned `AX` | Next active state |
|---:|---:|---|
| Seed | — | `78 56 34 12 00` |
| 1 | `788B` | `8B 78 56 34 12` |
| 2 | `8BD2` | `D2 8B 78 56 34` |
| 3 | `D25E` | `5E D2 8B 78 56` |
| 4 | `5E2D` | `2D 5E D2 8B 78` |

### BIOS-clock seed and repeatability

The startup call at runtime `CS:008A` invokes the only direct seed call, `CS:2916`. That routine reads the BIOS tick dword from `0040:006C` and copies it little-endian into the first four active bytes:

```text
q0 = tick bits  0..7
q1 = tick bits  8..15
q2 = tick bits 16..23
q3 = tick bits 24..31
q4 = unchanged
```

The image initializes scratch and all five active bytes to zero, so `q4` is zero when a fresh process reaches the seed routine. Identical BIOS tick values therefore produce identical initial states and output streams on fresh launches. A later reseed would retain the then-current `q4`, but no later direct seed call exists.

Repeatability after startup also depends on call order because all consumers share this state. The first frontend background consumes a variable number of values before the 90 frontend stars receive their velocities. The star positions themselves are copied from embedded tables, while their velocities are generated. Thus an identical fresh seed and identical control path reproduce both the background and animation; reproducing a later game background additionally requires the same intervening random-call history. A saved full five-byte state at a named call boundary is sufficient for a focused mid-session comparison.

### Coordinate adapters and background distribution

The generator returns a 16-bit value, while the coordinate helpers apply their own masks and rejection intervals:

| Helper | Candidate | Accepted coordinates | Count |
|---|---|---|---:|
| `CS:28D0` X | `AX & 03FF` | `8..631` | 624 |
| `CS:28E1` Y | `AX & 01FF` | `8..191` | 184 |

Each helper retries until its candidate lies in the half-open accepted interval. If the masked values were uniform, one X result would require about `1024 / 624 = 1.64` generator calls and one Y result about `512 / 184 = 2.78`; these are conditional expectations, not a claim that this generator is statistically uniform.

Runtime `CS:2932` draws 512 pixels. For every pixel it obtains X, then Y, then calls the XOR pixel routine. Coordinates are therefore selected with replacement from the `624 x 184` interior. Duplicate coordinates are possible; because drawing uses XOR, an even number of hits at one coordinate leaves that pixel clear.

### Shared generator, caller-specific interpretation

The direct consumers do not use one universal range operation. They interpret raw bytes, words, or the coordinate adapters according to their own purpose:

| Consumer | Runtime call sites | Interpretation |
|---|---|---|
| Left robot decisions | `CS:0484`, `CS:0494` | Tests raw `AL < 0x10`, then separately tests `(AX & 0x03FF) == 0` |
| Right robot decisions | `CS:06B0`, `CS:06C0`, `CS:06E4` | Tests raw `AL < 0x10`, raw `AL < 0x08`, then `(AX & 0x03FF) == 0`; the extra right-side draw is a Phase 5 handoff question |
| Left hyperspace | `CS:0700`, `CS:071B` | Uses the rejecting X and Y coordinate helpers |
| Right hyperspace | `CS:0763`, `CS:077E` | Uses the same X and Y coordinate helpers |
| Round-end effects | `CS:087F`, `CS:08D3`, `CS:08DA` | Uses one bit from `AH` for sound and raw words for two star-velocity components |
| Frontend background | `CS:0956` | Draws 512 pixels through the coordinate helpers |
| Frontend star velocities | `CS:0A48`, `CS:0A51` | Arithmetic-shifts each raw word right once before storing signed X/Y velocity components |
| Game background | `CS:1F3C` | Draws another 512 pixels through the coordinate helpers |
| Randomized speaker divisor | `CS:289A` | ORs raw `AX` with `0x2000` before programming PIT channel 2 |

The shared generator is therefore a small service with deliberately thin caller-side mapping. Hyperspace and background placement share the bounded coordinate policy; stars, robot choices, and sound consume different portions of the raw result. The unequal robot call patterns are recorded here without assigning gameplay intent before P4-06 and Phase 5 inspect their surrounding decisions.

### Confidence and remaining questions

- Confidence is high in the storage layout, recurrence, return value, seed mapping, masks, rejection bounds, and direct-call inventory because each is encoded directly in the validated bytes.
- Confidence is high that a fresh launch with the same BIOS tick reproduces the initial stream because the retained state byte is initially zero and there is one direct seed call.
- The generator period and statistical quality have not been established; neither is needed to explain the code design or deterministic reproduction.
- Detailed 90-star position, fixed-point animation, and glyph behavior remain P4-05.
- The semantic reason for the left/right robot draw-count difference remains deliberately deferred to P4-06 and Phase 5.

## Evidence and uncertainty policy

- Use load-module offsets as the stable primary addresses and record Ghidra-space and runtime `CS:` mappings alongside them.
- Treat automatically created functions, signatures, types, and decompiler output as proposals until checked against instructions and control flow.
- Keep exact observed facts separate from inferred intent and attach a confidence level to architectural conclusions.
- Prefer static evidence in Phase 4. Any later debugger experiment must answer one named ambiguity and use the bounded workflow from `analysis/phase-3-findings.md`.
