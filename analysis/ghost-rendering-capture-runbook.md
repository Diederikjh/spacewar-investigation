# Ghost-Rendering State-Capture Runbook

## Purpose

Capture one useful post-event state without changing gameplay timing through
continuous breakpoints or a diagnostic executable. This is the first runtime
step after the focused static audit. Circular event logging remains a fallback
if a snapshot cannot distinguish the candidates.

Raw executable copies, state dumps, framebuffer dumps, screenshots, and run
manifests belong under ignored paths. Do not commit them.

## Capture set

Each useful stop needs four items associated with one run identifier:

1. a manifest containing the exact source-executable hash, play mode, option
   states, approximate elapsed time, hyperspace side/timing, whether the ghost
   persisted, and whether a round transition occurred;
2. the debugger register view, including runtime `CS`, `DS`, `SS:SP`, and the
   stopped `CS:EIP`;
3. `DS:0000..2AAF`, which covers the known mutable particle arrays, render
   parity, ship/entity state, options, shared counters, and random state; and
4. the 16 KiB CGA framebuffer at `B800:0000..3FFF`.

The data dump is deliberately broader than the named fields but remains small.
It protects the investigation from omitting an unknown shared byte. Only decoded
fields and changed ranges should later be supplied for analysis.

## X11 foreground and input rule

Never assume that either the DOSBox client or debugger terminal retained focus.
Use `analysis/scripts/ghost-capture-session.py` as the normal entry point. It
launches a uniquely titled debugger terminal, obtains the exact DOSBox process
identity from the launch script, discovers both X11 windows, and stores their
transient identifiers only in ignored session state. Before every action it
revalidates the DOSBox process/window relationship and the unique debugger
title. It refuses ambiguous, stale, or recycled targets.

```bash
analysis/scripts/ghost-capture-session.py launch
analysis/scripts/ghost-capture-session.py status
```

The driver does not interpret debugger pixels or decide whether an
acknowledgement is correct. Command typing and Enter are deliberately separate,
and the runbook's visual checkpoints still decide when the next action is safe.

### Hard stop on focus or input failure

Any failed focus check, nonzero input-action exit, or missing expected key is a
hard pause in the runbook. Stop before issuing another debugger or guest action
and notify the user which target and action failed. Do not retry automatically,
fall back to global input, redirect the key to another window, or continue on
the assumption that no input was delivered.

The user may bring the intended window forward or allow it to take focus. After
they confirm that intervention, run the session driver's focus-only action for
the intended target and require it to succeed:

```bash
analysis/scripts/ghost-capture-session.py focus dosbox
analysis/scripts/ghost-capture-session.py focus debugger
```

Retry the failed action only after that explicit confirmation and successful
focus-only check. If the failed action typed text, first inspect the debugger
input line for partial characters and correct or clear them before retrying; do
not blindly append the complete command. Repeat the normal visual checkpoint
after the retry. A second failure is another hard pause and must again be
reported rather than retried in a loop.

The session driver calls `analysis/scripts/x11-input.py` for each input action.
That lower-level helper asks the window manager to activate and raise the exact
target, assigns X input focus, verifies that the target received focus, and only
then emits input. A stale ID or failed focus check exits without emitting the
requested key.

Use the low-level helper directly only for troubleshooting a session that the
driver cannot manage. Resolve transient IDs after launch, keep the inventory out
of saved output, and never select by title alone when similarly named windows
may exist.

```bash
# Bring a window forward without sending input.
analysis/scripts/x11-input.py 0xWINDOW focus

# Type a debugger command without pressing Enter.
analysis/scripts/x11-input.py 0xWINDOW text 'bpint 3'

# After visually checking the command, reacquire focus and press Enter.
analysis/scripts/x11-input.py 0xWINDOW key Return

# Reacquire DOSBox focus and enter the debugger.
analysis/scripts/x11-input.py 0xWINDOW hotkey Alt_L Pause
```

For a key the human will press, run
`analysis/scripts/ghost-capture-session.py focus dosbox` immediately before
asking for that input. If any other window is selected in the meantime,
reacquire focus before accepting the key. These tools are specific to an X11
session and must fail closed rather than fall back to unverified global input.

## One-time rehearsal

Rehearse on an ordinary run before waiting for the anomaly:

1. From the repository root, launch a managed debugger session. The
   original-based working copy remains the default:

   ```bash
   analysis/scripts/ghost-capture-session.py launch
   ```

   To select another ignored build, pass its repository-relative source path:

   ```bash
   analysis/scripts/ghost-capture-session.py launch \
       --source analysis/work/SPACELEAD.EXE
   ```

2. Follow the entry-break procedure in this exact order:

   1. Run `analysis/scripts/ghost-capture-session.py open-debugger`.
   2. Run `analysis/scripts/ghost-capture-session.py type-breakpoint`, inspect
      the input crop, then run
      `analysis/scripts/ghost-capture-session.py submit-debugger`. Wait for
      `DEBUG: Set interrupt breakpoint at INT 03`.
   3. Run `analysis/scripts/ghost-capture-session.py resume-debugger` exactly
      once to return to the DOS `PAUSE`.
   4. Run `analysis/scripts/ghost-capture-session.py guest-key space` exactly
      once to start `SPACEBRK.EXE`.
   5. Run `analysis/scripts/ghost-capture-session.py focus debugger` and verify
      runtime `CS`, `EIP=00000000`, and `CD 03` at `CS:0000`. The breakpoint
      may stop execution without raising the debugger window.
   6. Do not resume. Run
      `analysis/scripts/ghost-capture-session.py type-restore-entry 044c`,
      replacing `044c` with the observed `CS`. Inspect the input crop and submit
      it separately. Verify both `DEBUG: Memory changed.` and `8CD8` in the code
      view.
   7. Type and submit `BPLIST` with `type-breakpoint-list` and
      `submit-debugger`. Remove its reported number with
      `type-delete-breakpoint <number>`, submit, and list again. Only after the
      list is visibly empty may `resume-debugger` continue to the frontend. All
      four names are subcommands of
      `analysis/scripts/ghost-capture-session.py`.

   Every `type-*` action deliberately omits Enter so command inspection remains
   a hard gate. `submit-debugger` reacquires and verifies focus independently.

   If `CS:EIP` is not the expected executable entry, stop and restart the
   disposable run. Continuing from an unverified entry can execute the injected
   bytes and produce a stream of illegal-instruction messages.
3. Select CPU-versus-CPU, keep the planet disabled, set the intended gravity
   option, and start play. The original-based, gravity-on sequence is four
   separate `analysis/scripts/ghost-capture-session.py` commands:
   `guest-key F3`, `guest-key F4`, `guest-key F6`, then `guest-key F2`.
4. At an arbitrary non-anomalous moment, run
   `analysis/scripts/ghost-capture-session.py open-debugger`. Do not first press
   the game's pause key because that changes guest state before capture.
5. Read the active `DS` value from the register view. Substitute that segment in
   the command below; `01a1` is an example and must be replaced with the active
   value:

   ```bash
   analysis/scripts/ghost-capture-session.py type-data-dump 01a1
   analysis/scripts/ghost-capture-session.py submit-debugger
   ```

6. In a separate host terminal, immediately archive the fixed debugger output:

   ```bash
   analysis/scripts/archive-debug-dump.sh rehearsal-001 data
   ```

7. Back in the debugger, type, inspect, and submit the CGA dump:

   ```bash
   analysis/scripts/ghost-capture-session.py type-cga-dump
   analysis/scripts/ghost-capture-session.py submit-debugger
   ```

8. Archive that output before issuing another dump:

   ```bash
   analysis/scripts/archive-debug-dump.sh rehearsal-001 cga
   ```

9. Confirm the archived sizes are `0x2AB0` and `0x4000`, respectively. Remove
   the rehearsal dumps after the workflow has been validated; they are not
   investigation evidence. End the disposable run with
   `analysis/scripts/ghost-capture-session.py close`. If the emulator was closed
   externally, use `analysis/scripts/ghost-capture-session.py cleanup` only
   after `status` reports it stale.

The debugger always uses the fixed name `MEMDUMP.BIN`. The archive helper moves
each output into `analysis/dumps/ghost-rendering/<run-id>/`, refuses to replace
an existing capture, validates `0x2AB0` for `data` or `0x4000` for `cga`,
restricts its permissions, and prints its checksum. The root fixed-name outputs
are ignored as an additional safety measure.

### Rehearsal result

The ordinary original-based rehearsal completed on 2026-08-15. It captured a
CPU-versus-CPU frame with gravity enabled and the planet disabled. The archived
data and CGA files had the expected sizes, and the data capture independently
confirmed robot-mode byte `03` at `DS:1076` and option byte `02` at `DS:2040`.
The disposable dumps were removed after validation.

The rehearsal also demonstrated that a breakpoint stop may not raise the
debugger window. An initial attempt therefore resumed a second time while
already stopped at `CS:0000`. The explicit entry verification and single-F5
guard above are required, not optional usability notes.

## Anomaly capture

For the first evidence run, avoid lifecycle breakpoints because they may change
the timing being investigated:

1. Create a unique run identifier and record the source path and SHA-256 before
   launch.
2. Run the selected executable in the observed CPU-versus-CPU configuration.
3. When the ghost becomes visible, use Alt+Pause immediately. Do not wait for
   hyperspace completion and do not press a guest key first.
4. Preserve a narrow original-resolution screenshot containing the game image,
   followed by a narrow debugger crop containing registers. Keep both local.
5. Dump and archive the data range as `<run-id>/data.bin`.
6. Dump and archive CGA as `<run-id>/cga.bin`.
7. Record whether the visible effect began at hyperspace entry, during particle
   movement, or on reappearance, and whether one or both ordinary ship shapes
   were affected.
8. Stop the run after capture. Do not resume and then treat the later state as
   belonging to the same event.

If no anomaly appears, retain only the compact manifest row and remove any
screenshots. A run with no state dumps does not need an empty dump directory.

## First interpretation

Decode these fields before considering a full trace:

- left/right visibility parity: `DS:0CBC` / `DS:0CCC` bit 0;
- hyperspace counters: `DS:0060` / `DS:0061`;
- current positions: `DS:0D1C..0D4D`;
- previous-rendered positions: `DS:0D5C..0D8D`;
- dirty bytes: `DS:0E1C` / `DS:0E2C`;
- entity bytes: `DS:0E3C` / `DS:0E4C`;
- current/previous angles: `DS:0E5C..0E8C`; and
- action/latch, energy, option, shared-tick, random, and particle state described
  in the static audit and architecture findings.

The first question is whether the framebuffer contains a ship-shaped XOR image
at a coordinate not represented by the logical current or previous-rendered
state. The second is whether the corresponding visibility bit agrees with the
image the foreground believes is present. A local decoder should produce only
these fields, candidate sprite locations, and a short discrepancy summary.

If the snapshot shows a parity/location mismatch, the next run should use the
narrow completion or entry breakpoints from the static audit. If state and
framebuffer agree despite the visible anomaly, prioritize emulator presentation
or a transient partial redraw and add a short rolling local visual capture before
instrumenting the executable.
