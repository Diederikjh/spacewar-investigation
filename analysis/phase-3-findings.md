# Phase 3 Findings: Controlled Runtime Investigation

## Status

Phase 3 is in progress. The isolated emulator setup, bounded baseline run, runtime entry capture, frontend timer correlation, and F2 Play transition are complete. Input-specific experiments remain pending.

The current gate is debugger interaction, not executable behavior: the normal DOSBox-X run reaches the game frontend, while the packaged DOSBox-X build does not expose a usable debugger in this environment. A lightweight DOSBox debug build provides the required command set, but its curses console should be run from a normal terminal rather than through an automated pseudo-terminal.

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
| P3-08 | Single input comparison | Send one movement key and one action key in separate bounded runs | Not started | Pending |

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
2. At the debugger's initial stop, enter `BPINT 3`, then press F5 to resume.
3. At the DOS `PAUSE`, focus the emulator window and press one key.
4. When interrupt 3 breaks at the executable entry, record `CS`. This debugger stops before executing the interrupt, so `EIP` should remain `00000000`.
5. Restore the original entry bytes with `SM <CS>:0000 8C D8`.
6. Verify the restored instruction with `C <CS>:0000`. Reset `EIP` only if it is not already `00000000`.
7. Set `BP <CS>:0940` and `BP <CS>:172D`, then press F5.
8. At the frontend, inspect interrupt vector 8 with `D 0000:0020`. The four bytes are the little-endian offset followed by the segment.
9. Set `BP <CS>:00BC` and `BP <CS>:233D`, press F5, then press F2 once in the emulator.
10. Stop after the first few game-timer hits. Do not enable an unrestricted trace.

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

## Expected address correlations

These remain hypotheses until P3-05 through P3-07 are complete:

| Runtime code offset | Proposed role | Dynamic confirmation |
|---|---|---|
| `0000` | Executable entry | Confirmed at `044C:0000`; original entry bytes restored |
| `0940` | Frontend entry | Confirmed at `044C:0940`, before frontend initialization calls |
| `172D` | Frontend timer handler | Confirmed at `044C:172D`; interrupt vector 8 contains `2D 17 4C 04` |
| `00BC` | Game entry | Confirmed at `044C:00BC` after exactly one F2 keypress |
| `233D` | Game timer handler | Confirmed at `044C:233D`; interrupt vector 8 contains `3D 23 4C 04` |
| `1F80` | Keyboard handler | Reserve for the later single-input experiments |

## Phase gate

Do not begin Phase 4 yet. Phase 3 should first complete the two single-input experiments. If the lightweight debugger behaves differently in a normal terminal, record the exact command and observed state in this document without adding host or package-version details.
