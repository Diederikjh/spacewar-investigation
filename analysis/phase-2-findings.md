# Phase 2 Static Code Map

## Result

The program is a compact, interrupt-driven assembly design with two main operating modes:

1. A frontend/attract mode driven by a dedicated timer handler.
2. A live game mode split between an interrupt-driven simulation and a foreground input/render loop.

The program installs its own keyboard handler for its entire lifetime. It swaps interrupt-8 timer handlers when moving between frontend and gameplay, and restores the original timer and keyboard vectors before exit.

No dynamic execution was used for these findings.

## Address convention

This document uses **load-module offsets** as the stable primary address. These are independent of the segment at which DOS loads the executable.

The MZ header is `0x200` bytes, and the code segment begins at load-module offset `0x2AB0`.

```text
file offset       = load-module offset + 0x200
runtime CS offset = load-module offset - 0x2AB0
```

Examples:

| Role | Load module | File | Runtime `CS:` offset |
|---|---:|---:|---:|
| Program entry | `0x2AB0` | `0x2CB0` | `0000` |
| Enter game | `0x2B6C` | `0x2D6C` | `00BC` |
| Frontend entry | `0x33F0` | `0x35F0` | `0940` |
| Frontend timer ISR | `0x41DD` | `0x43DD` | `172D` |
| Keyboard ISR | `0x4A30` | `0x4C30` | `1F80` |
| Game timer ISR | `0x4DED` | `0x4FED` | `233D` |

The runtime `CS:` offsets are the useful values for DOSBox-X breakpoints after the program's active code segment is known.

## Top-level control flow

```text
DOS entry CS:0000
  ├─ establish DS and custom stack
  ├─ verify and configure CGA
  ├─ save interrupt vectors 8 and 9
  ├─ program PIT channel 0 to about 72.8 Hz
  ├─ install keyboard ISR at CS:1F80
  └─ enter frontend at CS:0940
       ├─ install frontend timer ISR at CS:172D
       ├─ animate title, starfield, instructions, and distribution screens
       ├─ F1: restore platform state and exit
       └─ F2: reset stack and enter game at CS:00BC
            ├─ initialize live state from embedded template
            ├─ install game timer ISR at CS:233D
            ├─ foreground: input dispatch and XOR erase/redraw
            ├─ timer ISR: simulation, collision, timing, and sound
            └─ F1 or round end: return to frontend
```

Mode changes are deliberately non-local. The frontend timer handler recognizes the F1/F2 scan-code state and jumps directly to the exit or game entry path. Those targets reset the stack instead of returning through the interrupted frontend call chain.

## Interrupt and timing design

### Keyboard

The keyboard handler at load-module `0x4A30`:

- Reads scan code port `0x60`.
- Masks the scan code to `0..127` and stores the original make/break byte in a 128-byte table at `DS:1232`.
- Uses bit 7 directly: clear means pressed; set means released.
- Pulses keyboard controller port `0x61` and acknowledges the PIC at port `0x20`.
- Recognizes Ctrl-Alt-Delete and transfers to the reset vector.

The frontend and game do not call BIOS keyboard services. They read this shared scan-code table.

### Timer

PIT channel 0 is programmed with divisor `0x4006`, approximately 72.8 interrupts per second. Both custom timer handlers increment the BIOS tick count every fourth interrupt, preserving the conventional approximately 18.2 Hz DOS time base without chaining to the original BIOS handler.

The two timer modes are:

- `0x41DD` — frontend animation and F1-F8 option handling.
- `0x4DED` — gameplay simulation and audio update.

The original vectors are saved at startup. Shutdown restores both vectors and restores channel 0's default divisor.

## Frontend design

The foreground path at `0x33F0` cycles through several screens and animations:

- Title and copyright.
- Animated 90-particle title effect; Phase 4 later established that its glyph tiles form `SPACEWAR`.
- Player key assignments.
- Game instructions.
- User-supported distribution information.

The frontend timer handler independently animates the planet and handles the option keys:

| Key | Function inferred from code and embedded labels |
|---|---|
| F1 | Exit |
| F2 | Play |
| F3 | Toggle left robot player |
| F4 | Toggle right robot player |
| F5 | Toggle planet |
| F6 | Toggle gravity |
| F7 | Toggle pause |
| F8 | Toggle sound |

Edge-latch bits prevent one held key from toggling an option repeatedly. The display routine XORs the corresponding marker when a setting changes.

## Gameplay concurrency

The live game is divided across foreground and interrupt contexts.

### Foreground loop at `0x2B7D`

- Chooses human or robot control logic for each player.
- Dispatches nine configured actions per human player through compact call tables.
- Scans left projectile slots `0x02..0x0E` and right slots `0x12..0x1E`.
- XOR-erases objects using their previous position/frame.
- Snapshots current state under `CLI` and clears dirty flags.
- XOR-redraws objects at their new position/frame.
- Draws status indicators and round effects.
- Handles F1 return to frontend and F7/F8 pause/sound toggles.

### Game timer ISR at `0x4DED`

- Advances the global fixed tick.
- Maintains BIOS time every fourth tick.
- Applies player rotation and thrust.
- Advances fixed-point position and velocity.
- Wraps positions in a `640 x 200` world.
- Updates projectile lifetimes and positions.
- Applies collision and damage rules.
- Handles energy consumption and recharge intervals.
- Applies optional planet and gravity behavior.
- Updates sound selection and PC-speaker frequency.
- Marks objects dirty for the foreground renderer.

This is a producer/consumer arrangement over shared state. The timer produces new simulation state and dirty flags; the foreground consumes those flags to erase and redraw. Short `CLI` sections protect snapshots and slot activation/deactivation.

## Data design

### Broad layout

| DS range or base | Probable purpose |
|---|---|
| `0000..02AA` | Platform state and custom stack |
| `038D` and related arrays | Frontend title-particle positions and fixed-point motion |
| `0950..0CAF` | Embedded initial game-state template |
| `0CBC..101B` | Live copied game state |
| `1080` | Shared 72.8 Hz tick byte |
| `1085` | 200-entry CGA scanline-offset table |
| `1232` | 128-byte raw keyboard state table |
| `2040` | Planet and gravity option bits |
| `2050` | Signed angle/trigonometric lookup table |
| `2290..2292` | Sound event, sound phase, and sound-enabled state |
| `22A0` | 8-row character glyph data |
| `2AA0` | Random generator state immediately before code |

Code begins at load-module `0x2AB0`, directly after the primary data area.

### Parallel game-state arrays

Live entities are represented as parallel arrays rather than conventional contiguous records. A byte offset in `SI` selects the same logical entity across all arrays.

Examples include:

| Base | Observed role |
|---|---|
| `D1C` | Current X coordinate |
| `D3C` | Current Y coordinate |
| `D5C` | Previous rendered X |
| `D7C` | Previous rendered Y |
| `D9C` and `DDC` | X velocity/integrator components |
| `DBC` and `DFC` | Y velocity/integrator components |
| `E1C` | Render-dirty state |
| `E3C` | Active/type state |
| `E5C` | Current angle/frame |
| `E7C` | Previous rendered angle/frame |
| `EBC` | Action/motion flags |
| `F1C` | Energy, lifetime, or cooldown depending on slot |

Slot `0x00` is the left ship and slot `0x10` is the right ship. Slots `0x02..0x0E` belong to the left projectile pool; slots `0x12..0x1E` mirror them for the right player. The second-player logic commonly reuses the same array bases with `SI=0x10`.

Coordinates and velocities use split fixed-point components. Updates use paired `ADD`/`ADC` operations, allowing smooth motion while rendering at integer pixel positions.

## Rendering design

The game uses BIOS mode 6 followed by direct access to CGA memory at segment `B800`.

Important techniques:

- A 200-word table maps each Y coordinate to CGA's interleaved scanline banks.
- Pixel and sprite routines use XOR, so rendering the same object twice erases it.
- The world wraps at X `0x280` (640) and Y `0xC8` (200).
- Ships and projectiles select bitmap frames from angle/state values.
- A 16-frame planet renderer writes 32 scanlines directly.
- The frontend title effect uses 90 fixed-point glyph particles; the gameplay background draws 512 random pixels.

### Inline display data

The routine at `0x4732` implements an assembly-specific inline-data convention:

1. Caller loads display coordinates.
2. Caller invokes `CALL 0x4732`.
3. Null-terminated text or display-control bytes immediately follow the call instruction.
4. The routine pops the return address, consumes bytes from `CS`, pushes the updated address, and returns after the inline data.

This makes screens compact but interleaves data with executable code. Linear disassemblers therefore render large portions of strings and bitmap controls as nonsensical instructions, and automatic function-size results are not reliable without manual boundary correction.

## Audio and random services

Sound is produced through the PC speaker:

- Port `0x61` controls the speaker gate.
- PIT channel 2 is configured through ports `0x43` and `0x42`.
- A small event/phase state machine selects different fixed, swept, alternating, or random frequencies.
- F8 toggles the global sound-enabled byte.

The random generator maintains a compact five-byte additive/carry state seeded from the BIOS clock. It supports title and round-end particle velocities, background and hyperspace coordinates, robot choices, and randomized sound.

## Compiler and source-style assessment

Phase 2 strengthens the Phase 1 assessment that the program is handwritten or overwhelmingly assembly-based:

- No language runtime boundary exists between entry and application initialization.
- It manipulates interrupt vectors and return addresses directly.
- It uses custom calling conventions and register-passed parameters.
- Data is laid out as manually coordinated parallel arrays.
- Mirrored player logic is partly duplicated and partly selected by a shared byte offset.
- Inline data after `CALL` instructions is an intentional space-saving convention.

Confidence is high that conventional generated C runtime structure is absent. The exact assembler and linker remain unknown.

## File and resource behavior

No DOS file-service path or external resource filename has been identified. Text, font data, sprites, tables, state templates, and instructions all appear embedded in the executable. This supports a self-contained single-file design, though a focused DOS interrupt trace should verify the conclusion dynamically.

## Phase 3 breakpoint plan

The first dynamic session should remain bounded to startup and menu behavior:

1. Break at entry `CS:0000` and record the actual runtime code segment.
2. Break at frontend entry `CS:0940`.
3. Break at frontend timer handler `CS:172D` and verify the expected rate and option-state changes.
4. Trigger Play once and confirm the direct transition to `CS:00BC`.
5. Confirm interrupt vector 8 changes from `CS:172D` to `CS:233D`.
6. Stop after a few game timer ticks; do not trace a full session.

A later controlled input run can break at keyboard ISR `CS:1F80`, press one movement key, and compare the left-control dispatcher and timer-consumed state before and after that single action.

## Limitations

- Proposed names describe observed behavior and are not original symbols.
- Some fine-grained entity fields have overlapping meanings by slot and need runtime confirmation.
- Broad automatic function discovery is distorted by inline display data.
- Robot decision paths and all collision subtypes have not yet been named individually.
- Static evidence cannot confirm exact event timing under emulator scheduling.
