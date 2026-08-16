# Ghost-Rendering State-Capture Runbook

## Purpose

Capture post-event state while controlling how much the observation changes
gameplay timing. The first uninstrumented snapshot proved that the visible
anomaly is a set of stale XOR ship images. A later full-speed diagnostic run
captured the causal event sequence: hyperspace counters survive a round
transition even though the framebuffer and copied round state are reset.

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
transient identifiers and source-executable hash only in ignored session state.
Before every action it revalidates the DOSBox process/window relationship and
the unique debugger title. It refuses ambiguous, stale, or recycled targets.

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
3. On a fresh frontend with its default options, select CPU-versus-CPU, leave
   the planet disabled, and enable gravity in one focus-verified sequence:

   ```bash
   analysis/scripts/ghost-capture-session.py guest-option-sequence
   ```

   The helper raises and focuses the exact DOSBox window, verifies focus before
   every key, holds each of F3, F4, and F6 longer than an ordinary tap, and
   releases each key before sending the next. Capture the exact game window once:

   ```bash
   analysis/scripts/ghost-capture-session.py capture-options
   ```

   Inspect that ignored local image and verify the whole option row: both
   computer-player options on, planet off, gravity on. Only after that single
   checkpoint, start play separately with
   `analysis/scripts/ghost-capture-session.py guest-key F2`.

   These option keys toggle state. The sequence is valid only from a confirmed
   fresh default frontend. If it fails partway, stop, inspect the option row,
   and do not rerun the whole sequence blindly; otherwise already-applied
   toggles would be reversed.
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

1. Use the managed session identifier and recorded source SHA-256 as the run
   identity; record the intended play mode and options before starting play.
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

Run the repository-local decoder with the run identifier. `--write` also saves
the complete report as `decoded.json` inside the ignored capture directory:

```bash
analysis/scripts/decode-ghost-capture.py RUN_ID --write
```

The decoder validates both dump sizes, records their hashes, decodes the named
state, and tests the raw CGA framebuffer against all embedded left and right
ship frames. Its candidate threshold is intended to identify likely sprites for
human review, not to declare every partial cross-match a ghost.

If the snapshot shows a parity/location mismatch, the next run should use the
narrow completion or entry breakpoints from the static audit. If state and
framebuffer agree despite the visible anomaly, prioritize emulator presentation
or a transient partial redraw and add a short rolling local visual capture before
instrumenting the executable.

## First anomaly capture

The first evidence capture completed on 2026-08-15 using the gravity-edited
build, computer versus computer, gravity enabled, and the planet disabled. Raw
evidence and its manifest remain local under the ignored capture directory.

The stop occurred with the right effect at counter `20h`. Right entity, dirty,
and visibility state were all zero, and none of the 47 bits in its tracked
previous ship frame were present there. The right ordinary ship was therefore
correctly absent at this instant.

The left ship was active and consistently tracked at `(222,81)`: current and
previous-rendered positions matched, visibility was one, dirty was zero, and
59 of its 60 expected frame bits were present. The framebuffer also contained
two left frame-zero images at `(161,46)` and `(58,99)`, matching 56/56 and 55/56
sprite bits. Neither location appeared in the current or previous-rendered ship
state. This establishes genuine stale left-ship XOR images rather than a
particle cluster, background coincidence, or emulator-only presentation issue.

One stale image is adjacent to the template's `(160,46)` left start position.
Several preceding CPU-versus-CPU matches ended naturally, and the operator
relaunched play until the anomaly appeared during a later live match. It was not
observed at round end. Both frontend and game entry clear the complete CGA
framebuffer before drawing their new screen, so old pixels cannot cross that
boundary. The later circular trace nevertheless proved that the logical
hyperspace counters can cross it and recreate stale sprites in the fresh
framebuffer.

## Completion-breakpoint result

Eight left hyperspace completions were inspected across two launches of the
exact gravity-only build. All eight reached `CS:2630` with left visibility,
dirty, and entity state zero, and none showed a visible ghost. The samples do
not disprove the conditional completion candidate, but repeating the same
stopped experiment has diminishing value and may perturb the foreground/timer
ordering under investigation.

The second launch was deliberately ended by removing the completion breakpoint,
resuming, and sending F1. The DOSBox process exited before the expected frontend
confirmation. The synthetic key helper holds a key for 25 ms, which is long
enough for a plausible live-game-to-frontend transition followed by a second
frontend observation of the same F1 state. Treat this as a tooling hazard rather
than game evidence: do not use F1 to recycle full-speed diagnostic matches.
Allow CPU-versus-CPU rounds to end naturally, press F2 from the frontend, or
close the validated disposable session and launch a fresh one.

## Full-speed circular trace

### Build identity and scope

The first diagnostic image is derived only from
`analysis/work/SPACEGRAV.EXE`, SHA-256
`a8be13c10e4440615692b1a4dd580a9569cfc8a6178f7f9f434c0b0ea8bc8d50`.
That input contains `EDIT-GRAV-01` but does not compose either computer-player
edit. Generate the ignored diagnostic copy from the repository root:

```bash
analysis/scripts/instrument-ghost-trace.py \
    analysis/work/SPACEGRAV.EXE \
    analysis/work/SPACEGTR.EXE
```

The generator requires the exact input hash and guarded original bytes at every
hook. It expands a disposable copy while preserving all existing offsets, the
gravity routine, and the executable's word-sum convention. The ordinary gravity
build remains unchanged. The current generator output has SHA-256
`d690f339930eb80113c5531d7a90d57d7b07fa80eccf5ba4185d131097aa5089`.

The diagnostic image records five event types for both ships:

1. hyperspace entry after its counter becomes active;
2. one record before each timer-owned particle movement pass;
3. hyperspace completion before it erases particles or replaces ship state;
4. every actual ordinary ship XOR, before the visibility bit toggles; and
5. every completed ship render snapshot, after current state has replaced the
   previous-rendered state and dirty has been cleared.

The code occupies `CS:2AE4..2C71`. A 16-byte header begins at `CS:2E00`,
followed by 2,048 24-byte records at `CS:2E10..EE0F`. Each committed record
contains a sequence number, event, side, shared tick, both hyperspace counters,
visibility, dirty and entity state, current and previous angles, action and
latch bytes, entry flags, and current/previous X/Y coordinates for that ship.
The complete bounded dump is `0xC010` bytes.

No hook calls DOS, writes a file, or prints while gameplay runs. Record
reservation briefly masks interrupts; filling the reserved record restores the
caller's interrupt state and commits the event byte last. A nested timer event
therefore receives a different slot, and a partially filled final record can be
discarded safely. This is still an instrumented build: compare its reproduction
behavior with uninstrumented observations and use it to recover event order,
not by itself to attribute the defect to the original executable.

### Full-speed run and anomaly capture

1. Launch a fresh managed session with the diagnostic source and follow the
   existing one-time entry restoration procedure:

   ```bash
   analysis/scripts/ghost-capture-session.py launch \
       --source analysis/work/SPACEGTR.EXE
   ```

2. At a confirmed fresh frontend, run `guest-option-sequence`, then
   `capture-options` once to verify that F3/F4 are on, F5 is off, and F6 is on.
   Start play with a separate `guest-key F2`. Do not set lifecycle breakpoints.
   A partial option-sequence failure is a hard stop because repeating toggles
   blindly can invert the options that already succeeded.
3. Let the match run at full speed. Count completed matches and observed early
   hyperspace entries separately. Use natural round endings and F2 relaunches;
   do not use F1 to return from live play.
4. When a ghost is visible, immediately run `open-debugger`. Do not press a
   guest pause key first. Confirm that execution stopped and read the active
   runtime `CS` and `DS` values.
5. Type, visually verify, submit, and archive the trace before another dump:

   ```bash
   analysis/scripts/ghost-capture-session.py type-trace-dump RUNTIME_CS
   analysis/scripts/ghost-capture-session.py submit-debugger
   analysis/scripts/archive-debug-dump.sh RUN_ID trace
   ```

6. Capture and archive the ordinary data and CGA dumps using the established
   procedure. The run is useful only if all three files share the same run ID
   and execution was not resumed between them.
7. Decode the trace locally. The default report includes aggregate event and
   invariant counts plus only the latest 64 committed records:

   ```bash
   analysis/scripts/decode-ghost-trace.py RUN_ID --write
   analysis/scripts/decode-ghost-capture.py RUN_ID --write
   ```

8. Stop the disposable run after capture. Keep the diagnostic executable, raw
   trace, memory dumps, framebuffer dump, screenshots, and decoded full reports
   under ignored paths.

For a clean run, retain only compact counts: exact build hash, matches,
hyperspace entries and completions per side, whether the buffer wrapped, and
whether any invariant warning occurred. Do not retain screenshots or empty raw
capture directories.

### Instrumented reproduction result

The third full-speed CPU-versus-CPU round produced a visible anomaly within
approximately the first second. The operator identified the affected player as
left. The archived framebuffer confirms that the two extra shapes are perfect
left-player frame-zero masks at `(164,46)` and `(59,131)`. The ordinary right
sprite at `(226,137)` is the legitimate active right ship.

The circular trace recovered the minimal sequence without resuming execution:

1. The preceding round ended while hyperspace was active. During its final
   gameplay-timer interval the counters reached left `44` and right `8`.
2. The next game entry cleared the framebuffer and copied the new round
   template, but did not clear `DS:0060/0061`. Its initial left and right ship
   draws therefore occurred while those stale counters were still nonzero.
3. The timer resumed the old left effect over the new round. At trace sequence
   8293, left completion saw the new left ship active and visible at `(164,46)`
   rather than absent with visibility zero.
4. Completion replaced the live ship coordinates with the old particle result
   `(59,131)`. Subsequent XOR and snapshot events stranded frame-zero images at
   both coordinates.
5. A later right hyperspace request also started from a stale nonzero counter,
   confirming the same lifecycle failure independently on that side.

The trace contained 2,048 committed records with no incomplete records or
sequence gaps. Its invariant summary reported 65 timer movements while a ship
was active, one active-entity/visibility failure at completion, one later entry
from an already nonzero counter, and three initial ship draws with nonzero
hyperspace counters. The finding explains why the anomaly clusters around early
hyperspace after relaunches: framebuffer pixels do not survive the transition,
but effect counters do, and the resumed effect corrupts the fresh round's XOR
render state.

### Original-executable reproduction result

The unmodified original was later reproduced repeatedly in human-versus-human
mode by starting hyperspace, pressing F1 before completion, and starting a new
round with F2. The old animation remained frozen while the frontend was open,
resumed only after gameplay restarted, and then stranded a ghost at the
affected ship's default start position. Different frontend wait times did not
advance the effect. The final live position sometimes resembled the previous
hyperspace destination but varied and was not the exact selected coordinate.

This is now the smallest manual regression case. A counter-reset prototype
should run it for left and right ships, immediate and delayed F2 restarts, and
require no inherited particle movement or default-position ghost.
