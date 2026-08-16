# Ghost-Rendering Focused Static Audit

## Status and outcome

The static gate and full-speed diagnostic follow-up are complete. The audit
found no direct overlap or state write from either `EDIT-CPU-06` lead prototype
into rendering or hyperspace state. The diagnostic trace then confirmed a
round-lifecycle defect in the investigated executable: game entry clears the
framebuffer and copies fresh entity state, but leaves the two hyperspace
counters outside that copy unchanged.

The resulting sequence is now established:

1. A round can end with `DS:0060` or `DS:0061` still nonzero.
2. Frontend and game entry clear old pixels, but neither resets those counters.
   The frontend may also reuse their shared particle arrays for the title.
3. A new round draws active, visible ships while the old effect remains
   logically active.
4. The gameplay timer resumes the stale effect. Its completion assumes that the
   corresponding ship is absent and its ordinary sprite parity is zero, then
   replaces current and previous-rendered coordinates.
5. Because the new ship is active and visible, that replacement breaks the XOR
   render invariant and strands ship images at the old and particle-derived
   coordinates.

The earlier entry deferred-erase gap remains real, and completion's assumption
about visibility remains the immediate parity failure. The trace explains how
completion can violate that assumption despite many foreground iterations: it
is completing an effect inherited from an earlier round against a newly active
ship, not racing the ordinary entry from the same round.

A separate shared-array hazard exists if a round ends while hyperspace is active.
The round-end effect and timer-driven hyperspace then use overlapping particle
arrays without mutual exclusion. This is a real code-design risk adjacent to the
confirmed cause. The visible ghosts appear during later live play, but the trace
shows that the causal state survives from an effect active across the preceding
round transition.

## Evidence boundary

The static portion re-read the original executable's instruction-aligned foreground,
hyperspace, timer, drawing, and round-end paths, then compared the owned regions
and register behavior of the earlier lead-only and expanded gravity-aware
`EDIT-CPU-06` patchers. The later runtime portion used a gravity-only diagnostic
copy with bounded in-memory lifecycle records and archived state/CGA captures.

The planet option was disabled in both reported sightings, and the visible
effect was away from the planet location. Planet drawing, gravity-independent
planet collision, and the planet's direct-writer renderer are not priority
candidates for the first runtime check.

### Informal runtime update

After this audit was planned, an informal comparison of approximately five
CPU-versus-CPU runs using a gravity-edited build and the original executable
suggested that roughly 30% of launches involving early hyperspace showed the
ghost effect. This is a useful reproduction clue, not a measured incidence
rate: the exact build hashes, number of runs per build, number of hyperspace
events, event-by-event outcomes, and whether the estimate refers to runs or
individual launches were not recorded.

The observation strengthened the association with hyperspace shortly after
game entry and weakened explanations that require a planet interaction. At this
stage it did not independently establish an original-executable outcome; the
later controlled F1/F2 reproduction below now supplies that evidence.

## State involved

| State | Left | Right | Role |
|---|---:|---:|---|
| Sprite visibility parity | `DS:0CBC` bit 0 | `DS:0CCC` bit 0 | Toggled by every ordinary ship XOR; wrappers use it to ensure drawn or erased state |
| Current X/Y | `DS:0D1C` / `DS:0D3C` | `DS:0D2C` / `DS:0D4C` | Timer-owned live integer coordinates |
| Previous-rendered X/Y | `DS:0D5C` / `DS:0D7C` | `DS:0D6C` / `DS:0D8C` | Coordinates used by ordinary ship XOR rendering |
| Dirty byte | `DS:0E1C` | `DS:0E2C` | Requests erase, snapshot, and redraw |
| Entity state | `DS:0E3C` | `DS:0E4C` | Zero while the ship is absent in hyperspace |
| Current/previous angle | `DS:0E5C` / `DS:0E7C` | `DS:0E6C` / `DS:0E8C` | Selects the current and previous ship sprite frame |
| Hyperspace counter | `DS:0060` | `DS:0061` | Zero when inactive; advances through the timer-driven particle effect |

The six mutable 90-word particle arrays begin at `DS:038D`, `0441`, `04F5`,
`05A9`, `065D`, and `0711`. Left hyperspace uses even byte indices
`00..3E`; right hyperspace uses `40..7E`. Those two 32-entry slices do not
overlap. The round-end effect uses all indices `00..B2` and therefore overlaps
both hyperspace slices.

## Ordinary dirty redraw invariant

The visibility byte is a parity tracker, not a stored coordinate. Bit 0 is
toggled at `CS:1BE5` immediately before the renderer XORs the selected ship
sprite. The four wrappers are:

| Operation | Left | Right |
|---|---:|---:|
| Ensure drawn | `CS:1B7E` | `CS:1B76` |
| Ensure erased | `CS:1B8E` | `CS:1B86` |
| Ship XOR entry | `CS:1B9F` | `CS:1B96` |

For an active, visible, dirty ship, the foreground path:

1. ensures the previous sprite is erased;
2. calls `CS:022E`, which copies current X/Y/angle to the previous-rendered
   fields and clears dirty under `PUSHF; CLI; ...; POPF`; and
3. ensures the new previous snapshot is drawn.

Left uses foreground `CS:00F4..0104`; right uses `CS:0168..0178`. Timer
interrupts may occur during either XOR operation or between erase, snapshot, and
draw. The timer saves and restores all registers used by the renderer. If it
moves a ship during those windows, it sets dirty again; the next foreground pass
then repeats the transition. No parity loss follows from ordinary movement alone.

The short interrupt exclusion protects the snapshot copy and dirty clear, not
the two XOR operations. That is sufficient for ordinary motion because the
timer does not change entity state to inactive or overwrite previous-rendered
coordinates. Hyperspace has different state transitions and is the important
exception.

## Hyperspace entry: definite deferred erasure

The left and right triggers at `CS:06F6` and `CS:0759` begin with:

```text
CLI
entity_state = 0
dirty = 0
STI
```

They do not call the ordinary ensure-erased wrapper and do not clear the
visibility parity flag. Each trigger then selects a destination, calculates
drift from the previous-rendered coordinates, initializes its 32-entry particle
slice at those previous coordinates, XORs the 32 initial points, and finally
increments its counter at `CS:074F` or `CS:07B2`.

All 32 initial points occupy the same pixel. XORing that pixel an even 32 times
leaves the framebuffer unchanged until the first timer movement separates the
particles.

The foreground decided that the ship was active before calling its control
routine. It does not repeat that entity test after the control routine returns.
For a non-cloaked ship, the trigger has cleared dirty, so the remainder of the
same foreground pass merely calls ensure-drawn. Because the visibility bit is
normally already one, that call is a no-op. The ordinary ship is erased only on
the next foreground pass:

| Stage | Left | Right |
|---|---:|---:|
| Active test before control | `CS:00DB` | `CS:014F` |
| Control call | `CS:00E4` | `CS:0158` |
| Same-pass ensure drawn | `CS:0104` | `CS:0178` |
| Next-pass inactive ensure erased | `CS:00EE` | `CS:0162` |

There is consequently a real interval in which `entity_state == 0`, `dirty ==
0`, and the ordinary visibility flag remains one. A timer tick in that interval
can begin moving the hyperspace particles while the old ship sprite remains on
screen. This is a plausible explanation for a very brief old-ship-plus-particle
blip. It does not by itself explain a lasting duplicate of both ships.

The window is longer for a left trigger because the rest of the left entity
loop, the complete right control/render work, and shared foreground work occur
before the next left active test. A right trigger occurs later in the foreground
iteration and normally has a shorter deferred-erase window.

## Hyperspace completion: conditional stranded sprite

The timer owns completion atomically with respect to the foreground. Left
completion begins at `CS:2630`; right completion begins at `CS:2732`. Each path:

1. XOR-erases all 32 current particle pixels;
2. clears the hyperspace counter;
3. sets dirty and entity-active bits;
4. copies the first particle position into both current and previous-rendered
   ship coordinates; and
5. clears the ship's velocity and particle drift.

It does not verify or reset `DS:0CBC/0CCC`. This is correct only if the deferred
ordinary ship image was erased and its visibility bit reached zero earlier.

If completion is entered with the visibility bit still one, it overwrites the
only coordinates that identify the old visible sprite. On the next dirty pass,
ensure-erased XORs a ship at the newly restored coordinates, toggles the flag to
zero, and ensure-drawn XORs the same location again. Those two new-location XORs
cancel one another while the old sprite remains in the framebuffer. Later dirty
passes can then produce a real ship plus stale images because the parity flag no
longer describes the location of the visible XOR.

Reaching completion before any foreground inactive pass would require roughly a
full hyperspace cycle without closing the entry window. That is unlikely during
ordinary unpaused play. A non-local transition, foreground starvation, or a
shared-effect interaction would be needed; this is why the condition should be
checked at completion rather than assumed to be the observed defect.

## Shared particle arrays and transition audit

The live left and right hyperspace loops use correct, non-overlapping slices:

- left initializes and advances 32 entries at `00..3E`;
- right initializes and advances 32 entries at `40..7E`;
- loop bounds increment the byte index by two exactly 32 times; and
- completion restores left from particle `00` and right from particle `40`.

No wrong-side base, one-entry overlap, or midpoint/completion off-by-one was
found. Simultaneous left/right hyperspace is data-safe, although both ordinary
ship images can remain visible until their next foreground inactive passes.

The round-end effect at `CS:07FC` is different. It initializes and animates all
90 entries while the gameplay timer remains installed. It does not first clear
`DS:0060/0061`. If a round ends during hyperspace, the foreground round-end loop
and timer can erase, move, and redraw the same particle entries with different
algorithms. This can break XOR parity and corrupt positions. It also supplies a
path that can prevent the ordinary next-pass erasure assumed by hyperspace
entry. The later screen transition may hide the damage, but this interaction is
a concrete defect candidate for any sighting near a death or round transition.

The diagnostic trace now connects the persistent counters to a preceding round
transition, although it does not prove that shared-array interference is needed
to create the later ghosts. Counter survival alone is sufficient: after game
entry draws fresh active ships, the stale timer effect violates completion's
entity/visibility assumptions. A robust repair should nevertheless cancel the
effect before round-end code reuses the arrays.

## Lead-edit audit

Both observed edit generations share these changes:

- `CS:05E9..05F8` replaces four raw X/Y delta instructions in the right
  computer-player policy with a near call and padding;
- the helper returns the expected `CX:DX`, leaves `BP` unchanged at zero, clears
  `BX`, and balances its temporary `PUSH CX`; and
- it does not call the random generator or write entity, dirty, visibility,
  hyperspace, particle, framebuffer, option, or latch state.

The earlier lead-only helper occupies `CS:2AE4..2B4F`. The expanded
gravity-aware helper occupies `CS:2AE4..2B5F`. Both ranges are separate from the
foreground, hyperspace, timer, rendering, data, and private-stack regions. The
expanded file preserves every existing offset and address.

No downstream dependency on the helper's changed `AX` value was found. The
following bearing code establishes its own flags immediately and defines `AL`
or `AX` before using it. The lead helper can take longer than the four replaced
loads and can therefore shift the phase at which timer interrupts meet the
foreground. Timing exposure remains possible, but direct rendering-state
corruption by the patch is a low-confidence hypothesis after this audit.

Because the lead helper runs before the later random hyperspace decision, its
additional time does not directly lengthen the post-trigger window for a right
computer player. It can lengthen the same foreground iteration after a left
computer player triggers hyperspace, because right-player control occurs later
in that iteration.

## First uninstrumented anomaly snapshot

An ignored gravity-edited run was frozen while the anomaly was visible and then
captured without lifecycle breakpoints. The data itself records computer versus
computer mode (`DS:1076 == 03`) with gravity enabled and the planet disabled
(`DS:2040 == 02`). This corrects any visual assumption that the capture was a
human-versus-computer round.

At the stop, the right hyperspace counter was exactly `20h`. Right entity,
dirty, and visibility state were zero. Its tracked previous-rendered position
was `(228,153)`, angle `B5`, and embedded right frame 11; the CGA framebuffer
contained zero of that frame's 47 set bits at the tracked location. The capture
therefore does not exhibit the conditional right-completion parity failure.

The left ship was active with visibility one and dirty zero. Current and
previous-rendered positions both held `(222,81)`, current and previous angle
both held `35`, and the framebuffer contained 59 of the expected 60 left frame
3 bits at that location. This is a consistent ordinary ship draw.

A scan using the executable's embedded ship masks found two additional left
frame-zero images:

| Coordinate | Matching sprite bits | Represented by live ship state? |
|---:|---:|---|
| `(161,46)` | `56/56` | No |
| `(58,99)` | `55/56` | No |

The near-complete masks and their absence from both current and
previous-rendered coordinates establish stranded left-ship XOR images. They are
not a 32-pixel hyperspace cluster, random-background interpretation, adjacent
valid draw, or emulator presentation artefact. The first coordinate is next to
the template's `(160,46)` left start position. The exact creation transition was
not observed, and the concurrent right effect may merely have made the anomaly
easier to notice.

A focused transition re-check narrows that interpretation. Game entry copies
the template and then calls the full `0x4000`-byte CGA clear at `CS:1CD3` before
drawing the new background and initial ships. Frontend entry calls the same
clear before rebuilding its display. A completed restart therefore cannot
carry old framebuffer pixels into the new round. It can, however, carry the
logical counters at `DS:0060/0061`, which lie outside the copied state and are
not cleared by either transition. The later instrumented run confirmed that
this surviving state recreates stale images after the new screen is built.

The operator later clarified the run history: several earlier
CPU-versus-CPU matches ended naturally, then new matches were launched until the
anomaly appeared during ordinary live play. It did not appear at round end.
The later trace explains that observation: the transition hides old pixels but
preserves active effect counters, so the visible corruption is created only
after the new round begins.

## Instrumented reproduction and confirmed cause

A gravity-only diagnostic copy reproduced the anomaly on the third
CPU-versus-CPU round, within approximately the first second. The frozen trace,
data segment, and CGA image were captured without resuming between dumps.

The 2,048-record circular buffer had wrapped normally, with no incomplete
records or sequence gaps. Its decisive sequence was:

- a preceding round ended with active hyperspace; the counters later visible at
  the new-round boundary were left `44` and right `8`;
- initial left and right ship draws in the fresh round occurred at trace
  sequences 8221 and 8222 while both counters were still nonzero;
- at sequence 8293, stale left completion saw entity state one, visibility one,
  dirty zero, and current/previous position `(164,46)`;
- completion replaced that position with particle result `(59,131)`, after
  which XOR/snapshot activity stranded left frame-zero sprites at both
  coordinates; and
- a later right request entered hyperspace while its inherited counter was
  already `53`, incrementing it to `54` rather than starting at one.

At capture, the current right ship was a legitimate frame at `(226,137)`. The
two apparent ghosts were instead perfect `56/56` left frame-zero masks at
`(164,46)` and `(59,131)`, matching the operator's corrected identification of
the affected player as left.

The decoder reported 65 hyperspace ticks while the corresponding ship entity
was active, one completion with an active entity and visible ordinary sprite,
one malformed later entry caused by an already nonzero counter, three initial
draws with a nonzero hyperspace counter, and no snapshot-coordinate invariant
failures. This confirms the counter carry-over as the root lifecycle defect and
the completion parity failure as its downstream rendering mechanism.

### Original-executable manual reproduction

The same defect was subsequently reproduced several times in human-versus-human
mode on the unmodified original executable, SHA-256
`2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490`:

1. Start a round.
2. Put either ship into hyperspace.
3. Press F1 while its particle effect is still active.
4. Start another round with F2.
5. Let the affected ship begin moving.

The remainder of the old particle effect appears during the new round and a
ghost is stranded at that ship's default starting position. Waiting different
amounts of time in the frontend did not advance the suspended effect. This is
consistent with the code ownership: only the gameplay timer advances
`DS:0060/0061`; the frontend timer leaves both counters unchanged.

The eventual live ship position can resemble the prior destination but is not
the actual selected coordinate and varied between repetitions. Normal
completion already restores from the first particle's final coordinate rather
than the exact selection. Across this boundary the new-round template also
replaces the ship velocity words that held the common destination drift, and
frontend display work may reuse the shared particle arrays. The surviving
counter therefore resumes an inconsistent mixture of old effect data and new
round state. The default-start ghost has a simpler explanation: game entry
draws the fresh ship at its template position before stale completion replaces
the render coordinates.

This reproduction closes the remaining attribution question: the lifecycle
defect exists in the original executable and does not require a prototype edit.

## Prototype repair

`EDIT-HYPER-02` implements the selected minimal repair by clearing both
hyperspace counters at round start before the original initializer draws either
ship. Its first controlled runtime run passed the left and right versions of
the reproduction above, directly observed both counter bytes as zero before
initialization, and completed one normal same-round hyperspace cycle per side.
Implementation, placement, validation limits, and reproduction details are in
[the focused edit findings](edit-hyper-02-findings.md).

## Completion-check history

Eight left completion stops at `CS:2630` were collected across two launches of
the exact gravity-only build. Each found visibility, dirty, and entity state
zero, and no stop showed a visible ghost. These bounded observations do not
prove that the conditional completion sequence is impossible, but they did not
reproduce it and breakpoint stops may change the foreground/timer phasing.

Those clean stopped samples are consistent with ordinary same-round
hyperspace. They did not exercise stale counters inherited by a fresh round,
which is why the later full-speed circular trace found the failure.

## Ranked candidates

| Rank | Candidate | Static confidence | Match to observations | Minimal next check |
|---:|---|---|---|---|
| 1 | Hyperspace counters survive the round/frontend boundary and resume against fresh active ships | Confirmed | The full-speed trace records nonzero counters at initial draws and an active-visible completion that produces the captured sprite coordinates | Design a guarded transition-state reset and validate repeated early relaunches |
| 2 | Same-round completion occurs while the ordinary visibility bit is still one | High consequence; not observed independently | This is the downstream mechanism in the confirmed cross-round sequence, but eight ordinary completion stops were clean | Retain as an invariant when validating the transition reset |
| 3 | Deferred ordinary-ship erasure lets a timer movement display hyperspace particles while the old sprite remains | High | Real transient window, but the confirmed lasting ghosts came from inherited counter state | Keep as a separate possible one-frame visual blip |
| 4 | Round-end foreground animation races an active timer hyperspace effect in the shared 90-entry arrays | High | A real related hazard, but the confirmed F1/F2 ghost requires only a retained counter | Track separately; it is not required for the selected round-start reset |
| 5 | Old framebuffer pixels cross a completed transition | Disproved for the captured path | Both entries clear the full CGA aperture; only logical effect state crosses | Preserve the framebuffer-clear check in validation |
| 6 | Lead helper changes foreground/timer phasing and exposes an original timing window | Medium | Timing can change incidence, but the captured build has gravity only and the lifecycle defect is original code | Compare unmodified incidence only if attribution is needed |
| 7 | Prototype code directly corrupts hyperspace or render state | Low | No relevant prototype write; the defective counters and transitions are original paths | Revisit only if a patched lifecycle differs with identical pre-state |
| 8 | Planet renderer or collision interaction | Low | The capture independently confirms planet disabled | Keep planet disabled in transition-reset validation |

## Narrow runtime handoff history

The original post-audit handoff used the following bounded checks before
escalating to a circular trace. The completion check in step 3 produced eight
clean samples. The circular trace later superseded the unresolved handoff and
recovered the transition ordering.

Before interpreting another percentage, keep a one-line local record per run:
exact executable hash, options, play mode, elapsed time to each hyperspace entry,
side, whether the effect appeared, whether it persisted beyond the particle
cycle, and whether a round transition occurred. Report numerator and denominator
separately for each build.

1. Rehearse the left-side lifecycle on an original-based run copy. At
   `CS:0753`, immediately after counter activation, record `DS:0060`, `0E1C`,
   `0E3C`, `0CBC`, `0D5C`, and `0D7C`. The expected transient state is counter
   one, dirty zero, entity zero, and visibility commonly still one.
2. Establish whether the first left timer movement at `CS:25B5` can occur
   before the next foreground inactive-erase call at `CS:00EE`. This is an
   ordering observation, not a long instruction trace.
3. In a separate minimally perturbed run, break only at left completion
   `CS:2630`. The critical invariant is `DS:0CBC == 0` before completion replaces
   the render snapshot. The right-side invariant remains useful as a later
   matched control, but the first captured stale images use left masks.
4. Compare the same completion invariant on the exact lead-only and expanded
   gravity-aware builds. Record build hashes and options, but do not dump the
   full data segment unless a completion stop finds a nonzero visibility bit or
   inconsistent snapshot.
5. If completion always sees zero, treat the stranded-sprite sequence as
   unobserved and move next to a locally captured entry window. Broad circular
   logging remains a later fallback.

These checks target the exact static ambiguity and should produce only a few
register/data rows per hyperspace event.
