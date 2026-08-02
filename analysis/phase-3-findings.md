# Phase 3 Findings: Controlled Runtime Investigation

## Status

Phase 3 is complete. The isolated emulator setup, bounded baseline run, runtime entry capture, frontend timer correlation, F2 Play transition, separate movement/phaser experiments, and controlled immediate exit all produced the required bounded evidence. No unrestricted trace or runtime dump was required.

The normal DOSBox-X run reaches the game frontend, while the packaged DOSBox-X build does not expose a usable debugger in this environment. The lightweight DOSBox debug route now provides the required command set; its curses console should be run from a normal terminal, and each breakpoint should be confirmed before execution resumes.

## Isolation and reproducibility

- `analysis/scripts/phase3-dosbox.sh` refreshes `analysis/work/dosbox-run/SPACEWAR.EXE` from the preserved working copy before each normal run.
- `analysis/config/dosbox-x.conf` mounts only `analysis/work/dosbox-run` as drive C.
- Emulator captures are directed to `analysis/traces/phase3`.
- The mounted directory, traces, dumps, logs, mapper files, and executable copies are excluded from version control.
- Both launchers change to the repository root before using repository-relative paths.
- No runtime dump is planned because Phase 1 established that the executable is not packed.

## Experiment log

| ID | Experiment | Bound | Result | Status |
|---|---|---|---|---|
| P3-01 | Isolated mount validation | Inspect the DOS mount and working-copy placement only | Drive C contains only the dedicated writable run directory | Complete |
| P3-02 | Baseline startup and idle | Start normally, observe the frontend and a short idle interval, then stop | CGA initialization succeeds; the instructions/options frontend is drawn; an idle interval advances to an animated demonstration with ships and scores | Complete |
| P3-03 | Packaged DOSBox-X debugger check | Test entry command, startup break, and debugger hotkey without tracing | Normal execution works, but `DEBUGBOX` is rejected and neither startup-break nor hotkey testing produced a debugger stop | Complete |
| P3-04 | Lightweight debugger command check | Start the alternate debug build without running a full game session | The debugger console and required `BP`, `BPINT`, `RUN`, `SM`, `SR`, and bounded logging commands are present | Complete |
| P3-05 | Runtime entry capture | Break at the executable entry and record the runtime code segment | Entry confirmed at `044C:0000`; original bytes restored before execution | Complete |
| P3-06 | Frontend timer correlation | Break at `CS:0940` and `CS:172D`; inspect interrupt vector 8 | Frontend entry and timer handler confirmed; vector 8 changed from `F000:FEA5` to `044C:172D` | Complete |
| P3-07 | Play transition | Press F2 once; break at `CS:00BC` and `CS:233D` | F2 reached game entry; vector 8 changed from `044C:172D` to `044C:233D` | Complete |
| P3-08 | Single input comparison | Send one movement key and one action key in separate bounded runs | `A` reached `044C:02B6`; `Q` reached `044C:0300` and changed energy/state before `044C:0316` | Complete |
| P3-09 | Immediate exit and crop validation | Press F1 once; bound shutdown and restoration; validate commands with narrow crops | F1 reached `044C:0095`; vectors 8 and 9 were restored before normal termination; crops caught incomplete input before Enter | Complete |

## Baseline observations

The normal run confirms that the static map describes executable code that is reached in practice:

- CGA mode setup succeeds under the constrained machine configuration.
- The first stable screen is the embedded instructions/options frontend identified during Phase 2.
- The visible function-key options match the statically identified frontend controls.
- Leaving the program idle produces an animated ship-and-score display, consistent with a timer-driven demonstration rather than a static menu loop.
- The run can be stopped without granting the DOS guest access to any directory outside `analysis/work/dosbox-run`.

These observations do not yet prove the proposed code addresses. That correlation is deliberately deferred until the entry runtime segment and timer-vector changes have been captured.

## Debugger route

`analysis/scripts/phase3-dosbox-debug.sh` supports a lightweight debug build when `dosbox-debug` is available. It creates `analysis/work/dosbox-run/SPACEBRK.EXE`, verifies that the entry bytes at file offset `0x2CB0` are `8C D8`, and changes only that ignored run copy to `CD 03` (`INT 03h`). The two-byte encoding is required because this debugger's `BPINT 3` does not intercept the one-byte `CC` encoding. The original and `analysis/work/Spacewar1985.exe` are not modified.

Use the following bounded procedure in a normal terminal:

1. Run `analysis/scripts/phase3-dosbox-debug.sh`.
2. At the DOS `PAUSE`, focus the emulator window and press Alt+Pause to open debugger command input.
3. Enter `BPINT 3`, verify the acknowledgement, then press F5 to resume.
4. Focus the emulator window and press one key to pass the DOS `PAUSE`.
5. When interrupt 3 breaks at the executable entry, record `CS`. This debugger stops before executing the interrupt, so `EIP` should remain `00000000`.
6. Restore the original entry bytes with `SM <CS>:0000 8C D8`.
7. Verify the restored instruction with `C <CS>:0000`. Reset `EIP` only if it is not already `00000000`.
8. Set `BP <CS>:0940` and `BP <CS>:172D`, then confirm them with `BPLIST` before pressing F5.
9. At the frontend, inspect interrupt vector 8 with `D 0000:0020`. The four bytes are the little-endian offset followed by the segment.
10. Set `BP <CS>:00BC` and `BP <CS>:233D`, confirm them with `BPLIST`, press F5, then press F2 once in the emulator.
11. Stop after the first few game-timer hits. Do not enable an unrestricted trace.

Key-release events generated while entering the debugger can remain queued for the guest. When investigating the keyboard handler, identify events by their scan-code byte rather than assuming the first stop belongs to the requested input. In this run, `BC`/index `3C` was F2 release and `B8`/index `38` was Alt release; neither was counted as movement evidence.

### Cropped-image command validation

Use local screenshot crops instead of OCR when the debugger terminal is being driven indirectly. Keep each crop at its original resolution and include only the evidence required for the current checkpoint:

1. After typing a command, inspect a crop containing the `->` input line and verify every character before pressing Enter.
2. Press Enter only while the debugger terminal is focused.
3. Inspect a crop of the latest output lines and confirm that the input line cleared and the expected `DEBUG:` acknowledgement appeared.
4. For breakpoints, run `BPLIST` and inspect a crop containing the exact registered address before pressing F5.
5. When execution stops, crop the `CS:EIP` registers, relevant code rows, and required data bytes separately. Use a larger crop or the full debugger window only when a narrow crop is ambiguous.

Do not resume execution when any checkpoint is missing. Store screenshots and crops only as temporary local files, remove them after validation, and do not add them to the repository.

When commands are driven indirectly, prefer individual key events over a batch of typed text. In P3-09, pre-Enter crops caught two incomplete commands (`B` instead of `BPINT 3`, and `d 00` instead of `d 0000:0020`). Both were corrected before Enter; the complete breakpoint set was then confirmed with `BPLIST`.

For a small trace around a confirmed breakpoint, use `LOGS 16` or another explicitly bounded instruction count. Raw logs belong under `analysis/traces/phase3` and must not be committed.

## P3-05 runtime entry

The breakpoint stopped before the injected `CD 03` instruction executed. The entry address is therefore confirmed without entering the BIOS interrupt handler:

| Register | Value |
|---|---|
| `EAX` | `00000000` |
| `EBX` | `00000000` |
| `ECX` | `000000FF` |
| `EDX` | `00000191` |
| `ESI` | `00000000` |
| `EDI` | `00000000` |
| `EBP` | `0000091C` |
| `ESP` | `00000000` |
| `DS` | `0191` |
| `ES` | `0191` |
| `FS` | `0000` |
| `GS` | `0000` |
| `SS` | `01A1` |
| `CS` | `044C` |
| `EIP` | `00000000` |

The segment values corroborate the MZ layout from Phase 1:

- `DS=ES=0191` identifies the DOS program segment at entry.
- The load-module base is `01A1`, `0x10` paragraphs (256 bytes) after the program segment.
- `CS=044C` equals load-module base `01A1` plus the header's initial `CS` value `02AB`.
- `SS=01A1` and `ESP=00000000` match the header's `SS:SP=0000:0000` relative to the load-module base.
- The first restored instruction at `044C:0000` is `8C D8` (`mov ax,ds`), confirming the entry mapping and preserving the DOS-provided data-segment value for startup.

## P3-06 frontend timer correlation

Execution first stopped at `044C:0940`, confirming the proposed frontend entry. The visible instructions begin by disabling interrupts, setting `SP=0166`, clearing frontend state, and calling the initialization routines identified in Phase 2.

At the frontend entry, interrupt vector 8 still contained bytes `A5 FE 00 F0`, which decode to the BIOS handler `F000:FEA5`. The adjacent interrupt vector 9 already contained `80 1F 4C 04`, confirming the keyboard handler at `044C:1F80` as an incidental cross-check.

After the frontend initialization calls ran, the next breakpoint stopped at `044C:172D`. At that stop:

- Interrupt vector 8 contained `2D 17 4C 04`, the little-endian pointer `044C:172D`.
- The runtime log reported PIT channel 0 operating in mode 3 at approximately 72.8 Hz.
- The handler began with register and segment preservation followed by its interrupt-controller acknowledgement path, matching the static ISR classification.
- `DS=B800` at interruption time shows that the timer interrupted foreground graphics work; the handler's prologue preserves that caller state before using its own data.

This confirms that frontend initialization replaces the BIOS timer vector with the proposed frontend timer handler and that the handler is reached at the programmed tick rate. No Play input was sent, so the proposed gameplay timer handler remains outside this experiment.

## P3-07 Play transition and gameplay timer

With breakpoints set at `044C:00BC` and `044C:233D`, one F2 keypress at the frontend stopped execution at `044C:00BC`. This confirms the proposed Play transition and game entry.

At the game-entry stop:

- Interrupt vector 8 still contained `2D 17 4C 04`, pointing to the frontend timer handler at `044C:172D`.
- The game startup reset `SP` to `0166`, cleared shared frontend/game state, and called the initialization sequence identified statically.
- That sequence included a call to `044C:1F14`, the proposed game-timer installer.

After resuming, the next timer breakpoint stopped at `044C:233D`. Interrupt vector 8 then contained `3D 23 4C 04`, the little-endian pointer `044C:233D`. Interrupt vector 9 remained `80 1F 4C 04`, so the keyboard handler continued at `044C:1F80` across the mode transition.

The game timer handler begins by preserving general and segment registers before loading the program data segment, matching the static classification of a substantial simulation ISR. The experiment stopped on this first confirmed game-timer hit; no movement or action input was sent.

## P3-08 single input comparison

The movement and action inputs were sent in separate bounded gameplay runs. Interrupt vector 8 contained `3D 23 4C 04` during the action run, independently confirming that the guest was using the gameplay timer handler at `044C:233D` rather than showing only the frontend demonstration.

### Movement: left-player A

One `A` input reached `044C:02B6`, the pressed-action target associated with scan code `1E` in the left-player key table. The handler contains two state changes:

- write `FE` (-2) to `[0E9C]`, the left-player rotation command;
- set bit 0 in `[0E1C]`, marking pending player state.

Execution was then bounded at `044C:02C1`. The rotation command had returned to zero by the later memory display. The most likely explanation is that the interrupt-driven simulation consumed the transient foreground command between the handler and the observation; this is an inference consistent with the producer/consumer design identified statically.

### Action: left-player Q

One `Q` input stopped at `044C:0300`, the pressed-action target associated with scan code `10` in the left-player key table. Before the handler ran, `[0F7C]=FF` allowed the action and `[0F1C]=7F` held the player's energy value.

A breakpoint at `044C:0316`, immediately before the handler's follow-up call, captured the bounded state change:

| State | Before `044C:0300` | At `044C:0316` |
|---|---:|---:|
| Energy `[0F1C]` | `7F` | `7E` |
| Phaser state `[0F7C]` | `FF` | `18` |

This confirms that the Q path spends one energy unit, arms a timed phaser state, and then calls a separate follow-up routine at `044C:2006`.

### Structural comparison

Both keys use the shared scan-code table and compact foreground dispatcher described in Phase 2, but they branch into distinct leaf handlers. Movement writes a transient command for later timer consumption, while the phaser action performs an immediate resource/state transition before calling a dedicated follow-up routine. This strengthens the proposed split between foreground input dispatch and interrupt-driven simulation.

## P3-09 immediate exit and cropped-image validation

One F1 input at the frontend stopped at `044C:0095`, confirming the direct shutdown target proposed in Phase 2. Before restoration, interrupt-vector memory contained:

| Vector | Bytes | Handler |
|---|---|---|
| 8 | `2D 17 4C 04` | Frontend timer `044C:172D` |
| 9 | `80 1F 4C 04` | Game keyboard `044C:1F80` |

The next breakpoint stopped at `044C:1EE2`, the routine that restores both vectors and writes the default divisor to PIT channel 0. A bounded stop at `044C:1F13`, immediately before the routine returned, showed:

| Vector | Bytes | Restored handler |
|---|---|---|
| 8 | `A5 FE 00 F0` | `F000:FEA5` |
| 9 | `87 E9 00 F0` | `F000:E987` |

After the final resume, execution continued through the mapped saved-stack and video-restoration sequence, returned through the DOS termination path, and the emulator session closed normally.

Only narrow original-resolution crops were inspected by the model. They preserved exact debugger glyphs while excluding unrelated terminal content. The command-line crop caught incomplete synthetic input before Enter on two occasions, while output, breakpoint-list, register, code, and data crops supplied sufficient evidence without OCR or full-window inspection. The approach reduced irrelevant visual context and improved correctness, although character-by-character synthetic input was slower than batched typing.

## Expected address correlations

The following runtime correlations have now been confirmed:

| Runtime code offset | Proposed role | Dynamic confirmation |
|---|---|---|
| `0000` | Executable entry | Confirmed at `044C:0000`; original entry bytes restored |
| `0940` | Frontend entry | Confirmed at `044C:0940`, before frontend initialization calls |
| `172D` | Frontend timer handler | Confirmed at `044C:172D`; interrupt vector 8 contains `2D 17 4C 04` |
| `00BC` | Game entry | Confirmed at `044C:00BC` after exactly one F2 keypress |
| `233D` | Game timer handler | Confirmed at `044C:233D`; interrupt vector 8 contains `3D 23 4C 04` |
| `1F80` | Keyboard handler | Persistent vector confirmed; post-store point `044C:1F95` distinguishes queued make/break events by scan code |
| `02B6` | Left-player rotate counter-clockwise | Confirmed after one `A` input |
| `0300` | Left-player phaser action | Confirmed after one `Q` input |
| `0316` | Phaser follow-up call site | Confirmed after energy changed `7F` to `7E` and phaser state changed `FF` to `18` |
| `0095` | Shutdown and exit | Confirmed after one F1 input at the frontend |
| `1EE2` | Restore vectors and PIT | Confirmed on the shutdown path before restoration |
| `1F13` | Restoration return | Confirmed after vectors 8 and 9 changed back to their saved handlers |

## Phase gate

The planned Phase 3 gate is satisfied, and Phase 4 is ready to begin with the reviewed Docker/Ghidra setup and scope in `analysis/investigation-plan.md`. Any later runtime trace should answer a specific new question and remain explicitly bounded.
