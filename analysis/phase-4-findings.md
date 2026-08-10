# Phase 4 Findings: Structured Ghidra Analysis

## Status

Phase 4 is complete. The approved pinned container and address model are validated, the high-confidence function map is applied, and the random, title/background, and computer-player handoff investigations are recorded below. Phase 5 can begin from exact decision entries, action leaves, state inputs, and random-call sites rather than from an unrestricted trace.

## Task log

| ID | Task | Evidence boundary | Status |
|---|---|---|---|
| P4-01 | Review the pinned Ghidra container setup | Select and record exact inputs, isolation, mounts, and storage before any download | Complete |
| P4-02 | Import and reproduce address mappings | Confirm the MZ loader, 16-bit real-mode language, entry point, and Phase 1/3 address conversions | Complete |
| P4-03 | Apply the static function map | Transfer high-confidence functions and subsystem boundaries from `analysis/function-ledger.csv` | Complete |
| P4-04 | Recover random-number design | Express seeding, the five-byte recurrence, caller range mapping, and repeatability | Complete |
| P4-05 | Recover star and background generation | Explain frontend star initialization/animation and gameplay background placement | Complete |
| P4-06 | Prepare the computer-player handoff | Identify decision entries, action leaves, state inputs, and random-number calls for Phase 5 | Complete |

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

At the P4-03 checkpoint, the tracked function ledger contained 53 proposed entries: 44 `high`, eight `medium-high`, and one `medium`. P4-03 applied only those 44 exact `high` rows. Phase 6 later refined one effect name and added the foreground collision and gravity families to the continuing ledger; those later rows were not part of the P4-03 label transfer.

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

Repeatability after startup also depends on call order because all consumers share this state. The first frontend background consumes a variable number of values before the 90 frontend title particles receive their velocities. The particle positions themselves are copied from embedded tables, while their velocities are generated. Thus an identical fresh seed and identical control path reproduce both the background and animation; reproducing a later game background additionally requires the same intervening random-call history. A saved full five-byte state at a named call boundary is sufficient for a focused mid-session comparison.

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
| Round-end sound choice | `CS:087F` | Uses one bit from `AH` for sound |
| Shared hyperspace/round-effect velocity initializer | `CS:08D3`, `CS:08DA` | Stores raw words as two pixel-velocity components; hyperspace initializes a 32-entry side-specific slice and round end initializes all 90 entries |
| Frontend background | `CS:0956` | Draws 512 pixels through the coordinate helpers |
| Frontend title-particle velocities | `CS:0A48`, `CS:0A51` | Arithmetic-shifts each raw word right once before storing signed X/Y velocity components |
| Game background | `CS:1F3C` | Draws another 512 pixels through the coordinate helpers |
| Randomized speaker divisor | `CS:289A` | ORs raw `AX` with `0x2000` before programming PIT channel 2 |

The shared generator is therefore a small service with deliberately thin caller-side mapping. Hyperspace and background placement share the bounded coordinate policy; stars, robot choices, and sound consume different portions of the raw result. The unequal robot call patterns are recorded here without assigning gameplay intent before P4-06 and Phase 5 inspect their surrounding decisions.

### Confidence and remaining questions

- Confidence is high in the storage layout, recurrence, return value, seed mapping, masks, rejection bounds, and direct-call inventory because each is encoded directly in the validated bytes.
- Confidence is high that a fresh launch with the same BIOS tick reproduces the initial stream because the retained state byte is initially zero and there is one direct seed call.
- The generator period and statistical quality have not been established; neither is needed to explain the code design or deterministic reproduction.
- Detailed 90-particle position, fixed-point animation, and glyph behavior are addressed in P4-05 below.
- The semantic reason for the left/right robot draw-count difference remains deliberately deferred to P4-06 and Phase 5.

## P4-05 title particles and backgrounds

### Evidence boundary and refined interpretation

The focused Ghidra export covered nine bounded routines, all nine 90-word particle arrays, the five selected 16-by-8 glyphs, and 21 reviewed direct calls. A byte-level sweep found exactly the same 21 direct-call candidates into the focused routines. The ignored report `analysis/ghidra/exports/p4-05-star-report.txt` contains the bounded bytes, complete 90-entry template, glyph bytes, a downsampled preview, and call validation; `analysis/ghidra-scripts/ExportStarDesign.java` reproduces it.

The earlier `starfield` and `xor_star` proposals remain useful navigation names, but P4-05 refines their meaning. The frontend object is a 90-tile animated title: its fixed template and five edge glyphs visibly form `SPACEWAR`. It is distinct from both the 512-pixel background and the later 90-pixel round-end effect.

### Nine parallel particle arrays

The title, hyperspace, and round-end effects share a compact structure-of-arrays block. Each array contains 90 words, occupies `0xB4` bytes, and is selected with an even byte index. The title and round-end paths can use all entries at `SI=0..0xB2`; left and right hyperspace reserve separate 32-entry slices within the mutable arrays.

| Initialized `DS:` base | Role | Image state |
|---:|---|---|
| `0171` | 16-by-8 glyph selector | Fixed template values `0x0E..0x12` |
| `0225` | Initial X integer | Fixed title template |
| `02D9` | Initial Y integer | Fixed title template |
| `038D` | Current X integer | Zero until initialized |
| `0441` | Current Y integer | Zero until initialized |
| `04F5` | Current X fractional word | Zero |
| `05A9` | Current Y fractional word | Zero |
| `065D` | Signed X velocity | Zero until generated |
| `0711` | Signed Y velocity | Zero until generated |

The mutable coordinate representation is 16.16 fixed point:

```text
X = (current_x_integer << 16) | current_x_fraction
Y = (current_y_integer << 16) | current_y_fraction
```

The code updates the low fractional word with `ADD` and the high integer word with sign extension plus `ADC`. This is the same split-word arithmetic style used by live game entities, but the particle arrays are separate from the entity arrays.

### Fixed `SPACEWAR` title template

Runtime `CS:0A1C` loops over all 90 entries. It copies the fixed X/Y templates into the current integer arrays, clears both fractional words, and XOR-draws each tile once.

All 90 positions are unique. Tile origins use a 16-pixel X grid from `64` through `560` and an 8-pixel Y grid from `80` through `112`. Because each tile is 16 by 8 pixels, the assembled title occupies X `64..575` and Y `80..119`, centered within the `640 x 200` display.

The selector counts are:

| Selector | Count | Shape role |
|---:|---:|---|
| `0x0E` | 47 | Solid 16-by-8 tile |
| `0x0F` | 11 | Wedge expanding toward one side |
| `0x10` | 6 | Mirrored expanding wedge |
| `0x11` | 19 | Wedge contracting toward one side |
| `0x12` | 7 | Mirrored contracting wedge |

Runtime `CS:1CB7` reads the current integer X/Y, shifts the selector left four bits to select a 16-byte glyph beneath `DS:22A0`, and invokes the eight-row XOR sprite renderer. These solid and diagonal-edge tiles combine to form the large `SPACEWAR` lettering without storing a conventional full-screen title bitmap.

### Disperse-and-reassemble animation

Runtime `CS:0A43` consumes two generator values per tile, 180 calls total. Each returned 16-bit word is arithmetic-shifted right once and stored as a signed velocity, giving the exact range `-16384..16383`.

Runtime `CS:0A87` renders 30 foreground frames. For every tile in every frame it:

1. checks the shared pause state;
2. XOR-erases the tile at its old position;
3. sign-extends each velocity, shifts it left three bits, and adds it to the corresponding 16.16 position;
4. XOR-draws the tile at its new position.

Thus each frame applies:

```text
X' = X + (signed_x_velocity << 3)
Y' = Y + (signed_y_velocity << 3)
```

This is at most two pixels of movement per axis per frame. Across 30 frames, the fixed title margins keep every 16-by-8 tile on screen, so this frontend routine needs no wrap or clipping branch.

The velocity initializer waits, runs one 30-frame outward animation, negates all 180 velocity components, and returns. Its frontend caller immediately invokes the same 30-frame animation again. Equal step counts with exactly negated velocities return every 32-bit fixed-point position to its starting value, reassembling the title without saving a second position snapshot.

The animation is foreground work rather than timer-driven work. Its only per-tile synchronization call waits while paused; the separate delay wrapper provides the longer holds between frontend displays.

### Hyperspace reuse of two 32-pixel slices

Hyperspace reuses the six mutable position, fraction, and velocity arrays, but it does not use the 90 fixed title positions, the glyph selectors, or the title's foreground animation routine. Each ship has a separate 32-pixel slice:

| Ship | Particle byte indices | Counter | Trigger |
|---|---:|---:|---:|
| Left | `00..3E` | `DS:0060` | `CS:06F6` |
| Right | `40..7E` | `DS:0061` | `CS:0759` |

The trigger first makes the ship inactive for ordinary control and rendering. It then chooses a bounded random destination through the shared X/Y coordinate helpers and calculates a signed 16.16 drift from the ship's previous rendered position to that destination:

```text
shared_drift_x = (selected_x - old_rendered_x) / 64
shared_drift_y = (selected_y - old_rendered_y) / 64
```

The integer delta is encoded exactly as a split 16.16 value by shifting its signed quotient into the high word and its remainder into the low word. The shared initializer at `CS:08B9` places all 32 pixels at the old rendered ship position, clears their fractional words, and stores two raw pseudorandom 16-bit words as each pixel's X/Y velocity. The trigger draws the initial pixels and advances the side-specific counter from zero to one.

The gameplay timer owns the remaining animation. On each movement step it XOR-erases a pixel, adds both its random component and the common destination drift, wraps the resulting integer coordinate, and XOR-redraws it:

```text
particle_x += 2 * random_velocity_x + shared_drift_x
particle_y += 4 * random_velocity_y + shared_drift_y
```

When the old counter value is `20h`, the timer negates all 32 stored random X/Y velocities before moving the pixels. The common destination drift is not negated. When the old value is `40h`, it erases the particles without another movement step, clears the effect counter, marks the ship active and dirty, and restores the ship at the first particle's final coordinate with zero velocity.

Because the trigger starts the counter at one and the timer compares the old value after incrementing the stored counter, the exact movement count is 31 steps with the original random velocities and 32 with their negations. The common destination drift is applied 63 rather than 64 times. Random motion therefore has a one-step residual, and the selected destination is an attractor rather than the exact restored coordinate. The first particle finishes near that destination, modulo screen wrapping, and determines the actual landing point.

This is an engineered spread-and-converge effect, not the title animation. The random-looking paths come from the shared deterministic generator; replay requires the same five-byte generator state and intervening call history.

### Round-end reuse of the mutable arrays

The round-end path at runtime `CS:07FC` reuses the six mutable position, fraction, and velocity arrays but not the fixed title positions or glyph selectors. Runtime `CS:08B4` places all 90 particles at one selected ship's previous rendered position, clears their fractional words, and stores two raw random words as signed velocities.

For 128 frames the round-end loop XOR-erases and redraws each particle as one pixel. It adds the signed 16-bit velocity directly to the 16.16 coordinate without the frontend's left shift, then wraps integer X at `640` and integer Y at `200`. A final 90-pixel XOR pass removes the effect. This produces a slower point-particle burst while reusing the same storage allocated for the title animation.

### Persistent random backgrounds

The 512-pixel background at runtime `CS:2932` is a third system. It does not use or populate any particle array. It obtains one accepted X/Y pair, immediately XORs that pixel into CGA memory, and repeats 512 times.

The frontend calls it at `CS:0956` after clearing the framebuffer. Game initialization calls it again at `CS:1F3C`, also after a clear and before status elements are drawn. The points then persist because their coordinates are not retained for movement or later erasure. As established in P4-04, duplicate coordinates are possible and XOR parity determines whether a multiply selected point remains visible.

| Property | Frontend title | Hyperspace | Round-end effect | Random background |
|---|---|---|---|---|
| Elements | 90 glyph tiles | 32 pixels per ship | 90 pixels | 512 draw attempts |
| Stored coordinates | All six mutable arrays | Left/right slices of the same arrays | All six arrays reused | None |
| Initial geometry | Fixed `SPACEWAR` template | Previous rendered ship position | One ship position | Random accepted X/Y |
| Motion | 30 frames out, 30 back | 31 spread steps, then 32 reversed steps with continuous destination drift | 128 wrapped frames | None |
| End state | Exact title reconstruction | Restore ship at first particle near selected destination | Final XOR erase | Persistent pixels |
| Renderer | 16-by-8 XOR glyph | XOR pixel | XOR pixel | XOR pixel |
| Boundary policy | Margins make wrapping unnecessary | Wrap `640 x 200` | Wrap `640 x 200` | Reject outer eight-pixel border |

### Confidence and handoff

- Confidence is high in the array layout, fixed-point formulas, frame counts, glyph dimensions, title reconstruction, velocity transformations, and background distinction because they follow directly from validated bytes and data.
- The ignored preview independently reconstructs readable `SPACEWAR` lettering from the fixed positions and glyph data; no screenshot interpretation is required.
- No debugger run is needed for P4-05. Timing in wall-clock terms remains emulator-speed dependent because the foreground animation is not paced by the custom timer.
- P4-06 can now treat the particle arrays as unrelated scratch/state storage when mapping computer-player inputs, avoiding confusion with the live entity arrays.

## P4-06 computer-player handoff

### Evidence boundary

The focused exporter validated the two complete control regions at runtime `CS:024F..04A5` and `CS:04A6..06F5`, both hyperspace implementations, the frontend robot-mode toggle region, four nine-entry action tables, the initial mode byte, both key-scan tables, the 32-word angle table, and 28 reviewed instruction-aligned direct calls made by the robot paths. The ignored report is `analysis/ghidra/exports/p4-06-computer-player-report.txt`; `analysis/ghidra-scripts/ExportComputerPlayerHandoff.java` reproduces its checks.

A raw byte search is not a valid completeness proof for calls in these regions. Four `E8` bytes inside other instructions resemble near calls when decoded without instruction alignment. The exporter therefore validates the reviewed call instructions but explicitly reports that it did not use a raw-byte sweep to claim completeness. The publishable address handoff is `analysis/computer-player-handoff.csv`.

### Mode selection and decision cadence

The initialized byte at `DS:1076` is zero, so both players default to human control. In the frontend timer path, F3 scan state at `DS:126F` toggles bit 0 at `CS:17A4`; F4 state at `DS:1270` toggles bit 1 at `CS:17C7`. Edge latches in `DS:107A` prevent one held key from repeatedly toggling the option.

| Side | Dispatcher | Human path | Robot path | Mode test |
|---|---:|---:|---:|---|
| Left | `CS:024F` | `CS:0259` | `CS:038E` | `DS:1076` bit 0 |
| Right | `CS:04A6` | `CS:04B0` | `CS:05E5` | `DS:1076` bit 1 |

The foreground game loop invokes the appropriate control routine once for each active ship before deciding whether cloak suppresses its rendering. Robot selection is therefore foreground-loop driven rather than directly timer driven. Individual effects remain constrained by shared state: energy transfers occur only when `(DS:1080 & 3) == 0`, and weapon or hyperspace helpers enforce their own energy, cooldown, allocation, and latch checks. Random consumption by robot decisions can consequently vary with foreground execution speed.

### Shared action surface

The human dispatch tables establish the same nine actions on both sides. They also give Phase 5 exact action leaves at which to compare a decision with its effect.

| Action | Left press | Right press | Effect |
|---|---:|---:|---|
| Rotate clockwise | `CS:02AA` | `CS:0501` | Store rotation command `+2` |
| Rotate counter-clockwise | `CS:02B6` | `CS:050D` | Store rotation command `-2` |
| Weapon to shield | `CS:02C2` | `CS:0519` | Transfer one unit per invocation while the shared tick is divisible by four |
| Shield to weapon | `CS:02E1` | `CS:0538` | Transfer one unit per invocation while the shared tick is divisible by four |
| Phaser | `CS:0300` | `CS:0557` | Spend one weapon-energy unit and start phaser state `0x18` when allowed |
| Photon | `CS:0320` | `CS:0577` | Allocate a free projectile when the latch permits |
| Impulse | `CS:034E` | `CS:05A5` | Set action-flag bit 0 |
| Cloak | `CS:0361` | `CS:05B8` | Set action-flag bit 1 |
| Hyperspace | `CS:0374` | `CS:05CB` | Spend eight energy units and enter hyperspace when the latch permits |

The human key order is `D A C Z Q E S W X` on the left and keypad `6 4 3 1 7 9 5 8 2` on the right. Phase 3 dynamically confirmed the left counter-clockwise and phaser leaves. Robot code reuses the energy, weapon, impulse, and hyperspace helpers, but directly commits its calculated aim instead of calling the gradual rotation leaves. Neither robot calls its cloak helper.

### Proposed state types

The robot code accesses the following initialized-data fields. Left uses entity slot `00`; right uses slot `10`. Array element widths vary by field, so the slot values below are byte indices used by the code rather than logical player numbers.

| Initialized `DS:` field | Proposed type and role | Robot use |
|---:|---|---|
| `1076` | `uint8` robot-mode flags | Dispatch bits 0 and 1 |
| `1080` | `uint8` shared tick | Four-tick energy-transfer gate in action helpers |
| `0D1C` / `0D2C` | `uint16` left/right X integer position | Threat or opponent delta |
| `0D3C` / `0D4C` | `uint16` left/right Y integer position | Threat or opponent delta |
| `0E1C` / `0E2C` | `uint8` render-dirty state | Set after direct aim change |
| `0E3C` / `0E4C` | signed byte entity active/type arrays | Ship and projectile eligibility |
| `0E5C` / `0E6C` | `uint8` ship angle | Direct robot aim target |
| `0E9C` / `0EAC` | signed byte rotation command | Cleared when robot commits aim |
| `0EBC` / `0ECC` | `uint8` action flags | Bit 0 impulse; bit 1 cloak |
| `0EDC` / `0EEC` | `uint8` action latches | Bit 0 photon; bit 1 hyperspace |
| `0EFC` / `0F0C` | `uint8` shield energy | Balance decision and helper checks |
| `0F1C` / `0F2C` | `uint8` weapon energy | Balance decision and zero-energy exit |
| `0F7C` / `0F8C` | `uint8` phaser state/cooldown | Enforced inside the phaser helper |
| `2250` | `uint16[32]` ratio-to-angle thresholds | Quantized bearing calculation |

Velocity, planet/gravity state, and world-wrap flags are not direct robot inputs. Cooldown, projectile allocation, and action-latch fields affect outcomes through the reused action helpers rather than through the decision branches themselves.

### Left defensive policy

The left path at `CS:038E` first tries to balance shield and weapon energy toward equality. If weapon energy is zero it disables impulse, takes the phaser release path, and returns.

It then scans the right-side entity slots `10, 12, ... 1E`. Slot `10` is the right ship; slots `12..1E` are its projectiles. A slot qualifies when its entity byte is active and non-negative and both raw absolute coordinate differences from the left ship are below `0x60`. It uses the first qualifying slot, so a nearby right ship has priority over every projectile and projectiles otherwise follow slot order. Distance does not use the world's wrapped shortest path. For a qualifying entity, the routine calculates a bearing, directly writes the left angle at `CS:046C`, marks the ship dirty, and invokes the phaser helper.

The path finishes with two independent random decisions:

- At `CS:0484`, raw `AL < 0x10` enables impulse; otherwise impulse is disabled.
- At `CS:0494`, `(AX & 0x03FF) == 0` requests hyperspace; otherwise it releases the hyperspace latch.

With no qualifying entity it skips aim and phaser work but still reaches both random movement decisions. It never selects photon or cloak. This close-range response to the opposing ship and its projectiles supports the executable's own description of the left robot as defensive.

### Right offensive policy

The right path at `CS:05E5` calculates raw signed X/Y differences from the right ship to the left ship and counts how many axes have absolute difference below `0x60`. It computes a bearing to the opponent, directly writes the right angle at `CS:0677`, marks the ship dirty, and then balances its two energy stores. If weapon energy is zero it disables impulse, releases photon, and returns.

Three random decisions follow:

- At `CS:06B0`, raw `AL < 0x10` enables impulse; otherwise impulse is disabled.
- At `CS:06C0`, `AL >= 8` releases both weapon actions. For `AL < 8`, two close axes select phaser while any other proximity count selects photon.
- At `CS:06E4`, `(AX & 0x03FF) == 0` requests hyperspace; otherwise it releases the hyperspace latch.

The right robot always aims at the opposing ship, uses both weapon helpers, never selects cloak, and consumes one more random value per full decision than the left robot. This control flow supports the executable's description of the right robot as offensive.

### Bearing calculation and asymmetries

Both paths take absolute X/Y magnitudes, retain quadrant information, compare the two axes, form a 16-bit fixed-point ratio, and use the 32 thresholds at `DS:2250` to quantize a bearing. They then store that bearing directly rather than requesting gradual rotation. Neither path corrects coordinate deltas for the toroidal playfield, so a target just across an edge can appear far away or in the longer direction.

The implementations share data layout, bearing machinery, energy balancing, movement probability, and hyperspace probability. Their principal difference is policy rather than simple mirroring: left fires phaser at the nearby opposing ship or, when the ship is not close, the first nearby opposing projectile; right always targets the opposing ship and probabilistically chooses phaser or photon according to axis-aligned proximity. The right-only weapon draw also advances the one shared random stream differently.

### Confidence and Phase 5 starting questions

- Confidence is high in the entry points, action addresses, state accesses, comparison constants, branch order, random call sites, and left/right policy difference because all are present in bounded bytes and validated aligned calls.
- `defensive` and `offensive` are supported interpretations from both behavior and embedded instructions; they are not recovered source-level names.
- The bearing's exact visual orientation and the practical effect of non-wrapped deltas are best expressed and tested in Phase 5 after normalizing the angle convention.
- The current static map is sufficient to begin Phase 5 without a broad debugger trace. Useful bounded experiments should target only remaining gameplay questions such as edge-wrap mis-aim, action cadence, or a proposed difficulty change.

## Evidence and uncertainty policy

- Use load-module offsets as the stable primary addresses and record Ghidra-space and runtime `CS:` mappings alongside them.
- Treat automatically created functions, signatures, types, and decompiler output as proposals until checked against instructions and control flow.
- Keep exact observed facts separate from inferred intent and attach a confidence level to architectural conclusions.
- Prefer static evidence in Phase 4. Any later debugger experiment must answer one named ambiguity and use the bounded workflow from `analysis/phase-3-findings.md`.
