# Ghost-Rendering Focused Static Audit

## Status and outcome

The first static gate is complete. The audit found no direct overlap or state
write from either `EDIT-CPU-06` lead prototype into rendering or hyperspace
state. It did find one definite transient invariant gap in the original
hyperspace entry sequence and one conditional way for that gap to become a
stranded XOR ship image:

1. A hyperspace trigger makes a ship inactive and clears its dirty byte before
   the ordinary ship sprite is necessarily erased. The old sprite remains until
   the next foreground pass notices the inactive entity.
2. Hyperspace completion assumes that erasure has happened. It does not inspect
   the sprite-visibility parity flag before replacing the previous-rendered
   coordinates. If the flag were still set at completion, the next erase would
   target the new coordinates and could leave the old sprite stranded.

The first condition is certain from the instruction order. The second is a valid
failure sequence but is not yet shown to occur during ordinary gameplay: under
normal scheduling, many foreground iterations should run during the 64-tick
hyperspace effect and erase the old sprite. The observations therefore remain
unexplained, but runtime work can begin with a few narrow lifecycle checks rather
than a large state logger.

A separate shared-array hazard exists if a round ends while hyperspace is active.
The round-end effect and timer-driven hyperspace then use overlapping particle
arrays without mutual exclusion. This is a real code-design risk, but it is a
weaker match for the reported sightings. The first captured anomaly is now
explicitly known to have appeared during a live match rather than at round end.

## Evidence boundary

This audit re-read the original executable's instruction-aligned foreground,
hyperspace, timer, drawing, and round-end paths, then compared the owned regions
and register behavior of the earlier lead-only and expanded gravity-aware
`EDIT-CPU-06` patchers. It did not run the executable, capture memory, or claim
that a candidate sequence has been reproduced.

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

The observation strengthens the association with hyperspace shortly after game
entry and weakens explanations that require a planet interaction or an observed
round transition. If the effect is visible immediately around entry, it also
fits the definite deferred-erase window better than the conditional completion
failure, which would require the ordinary erase to remain missing across the
full hyperspace cycle. The original executable's inclusion in the comparison is
important, but it is not yet evidence that the original independently exhibited
the effect until the per-build outcomes are separated.

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

No evidence currently connects a reported sighting to a round end. The first
captured anomaly was explicitly not observed during that transition. This
candidate should remain behind the ordinary entry/completion check unless a
future observation includes shield depletion, destruction, or a score change.

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
carry either stale image into the new round. The `(161,46)` frame-zero image is
instead consistent with the initial left ship moving one pixel and then being
stranded by a very early left hyperspace lifecycle. The exact creation event is
still unobserved.

The operator later clarified the run history: several earlier
CPU-versus-CPU matches ended naturally, then new matches were launched until the
anomaly appeared during ordinary live play. It did not appear at round end.
Together with the full framebuffer clears, this separates the captured defect
from those earlier matches and further deprioritizes the round-end shared-array
hazard for this sighting.

## Ranked candidates

| Rank | Candidate | Static confidence | Match to observations | Minimal next check |
|---:|---|---|---|---|
| 1 | Completion occurs while the ordinary visibility bit is still one, then overwrites the old render snapshot | High consequence; occurrence not yet observed | The captured framebuffer proves two untracked left sprites while the current left draw is consistent | Break only at left completion and inspect visibility plus the old and replacement snapshots |
| 2 | Deferred ordinary-ship erasure lets a timer movement display hyperspace particles while the old sprite remains | High | The frame-zero image one pixel from the initial left position fits a very early entry, but the short interval alone does not explain two lasting images | Observe left visibility parity at counter activation, first particle tick, and the next inactive foreground erase |
| 3 | Round-end foreground animation races an active timer hyperspace effect in the shared 90-entry arrays | High | A real separate hazard, but the captured anomaly appeared during live play and not at round end | Defer to a separate controlled round-end-during-hyperspace case |
| 4 | Round or frontend entry carries a stale image into the next screen | Low after transition re-check | Both entries clear the full CGA aperture before drawing new content | No runtime priority unless a controlled restart contradicts the clear path |
| 5 | Simultaneous CPU hyperspace leaves both old ordinary sprites visible for one foreground iteration | High | The capture is CPU versus CPU, but only the right counter was active at the stop and the lasting images are left sprites | Record both counters and visibility bits at entry |
| 6 | Lead helper changes foreground/timer phasing and exposes an original timing window | Medium | Timing exposure remains possible, but the captured build has gravity only rather than the lead patch | Compare matched original and gravity-edited lifecycle checks before attributing causality |
| 7 | Prototype code directly corrupts hyperspace or render state | Low | The captured stale left sprites do not map to a known gravity-patch write | Revisit only if a patched lifecycle differs with identical pre-state |
| 8 | Planet renderer or collision interaction | Low | The capture independently confirms planet disabled | Keep planet disabled in the next matched control |

## Narrow runtime handoff

The audit does not justify heavy state capture as the first runtime action. Use
the existing debugger workflow for these bounded checks:

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
