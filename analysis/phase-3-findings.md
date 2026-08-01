# Phase 3 Findings: Controlled Runtime Investigation

## Status

Phase 3 is in progress. The isolated emulator setup and a bounded baseline run are complete. Runtime segment capture, interrupt-vector confirmation, and input-specific experiments remain pending.

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
| P3-05 | Runtime entry capture | Break at the executable entry and record the runtime code segment | Pending a normal-terminal debugger session | Pending |
| P3-06 | Frontend timer correlation | Break at `CS:0940` and `CS:172D`; inspect interrupt vector 8 | Not started | Pending |
| P3-07 | Play transition | Press F2 once; break at `CS:00BC` and `CS:233D` | Not started | Pending |
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

`analysis/scripts/phase3-dosbox-debug.sh` supports a lightweight debug build when `dosbox-debug` is available. It creates `analysis/work/dosbox-run/SPACEBRK.EXE`, verifies that the entry byte at file offset `0x2CB0` is `0x8C`, and changes only that ignored run copy to `0xCC` (`INT 3`). The original and `analysis/work/Spacewar1985.exe` are not modified.

Use the following bounded procedure in a normal terminal:

1. Run `analysis/scripts/phase3-dosbox-debug.sh`.
2. At the debugger's initial stop, enter `BPINT 3`, then `RUN`.
3. At the DOS `PAUSE`, focus the emulator window and press one key.
4. When interrupt 3 breaks at the executable entry, record `CS`. `EIP` should be `00000001` because the breakpoint byte has executed.
5. Restore the original entry byte with `SM <CS>:0000 8C`.
6. Reset the instruction pointer with `SR EIP 00000000`.
7. Set `BP <CS>:0940` and `BP <CS>:172D`, then enter `RUN`.
8. At the frontend, inspect interrupt vector 8 with `D 0000:0020`. The four bytes are the little-endian offset followed by the segment.
9. Set `BP <CS>:00BC` and `BP <CS>:233D`, enter `RUN`, then press F2 once in the emulator.
10. Stop after the first few game-timer hits. Do not enable an unrestricted trace.

For a small trace around a confirmed breakpoint, use `LOGS 16` or another explicitly bounded instruction count. Raw logs belong under `analysis/traces/phase3` and must not be committed.

## Expected address correlations

These remain hypotheses until P3-05 through P3-07 are complete:

| Runtime code offset | Proposed role | Dynamic confirmation |
|---|---|---|
| `0000` | Executable entry | Record runtime `CS`, restore entry byte, and resume |
| `0940` | Frontend entry | Break after startup reaches the instructions/options screen |
| `172D` | Frontend timer handler | Confirm interrupt vector 8 and repeated frontend ticks |
| `00BC` | Game entry | Trigger exactly one F2 Play transition |
| `233D` | Game timer handler | Confirm interrupt vector 8 changes after Play |
| `1F80` | Keyboard handler | Reserve for the later single-input experiments |

## Phase gate

Do not begin Phase 4 yet. Phase 3 should first capture the runtime code segment, verify the frontend-to-game timer-vector change, and complete the two single-input experiments. If the lightweight debugger behaves differently in a normal terminal, record the exact command and observed state in this document without adding host or package-version details.
