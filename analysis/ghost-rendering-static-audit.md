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
weaker match for the reported sightings because neither report included an
observed round transition.

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

No evidence currently connects either reported sighting to a round end. This
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

## Ranked candidates

| Rank | Candidate | Static confidence | Match to observations | Minimal next check |
|---:|---|---|---|---|
| 1 | Deferred ordinary-ship erasure lets a timer movement display hyperspace particles while the old sprite remains | High | Plausible for a brief blip immediately after hyperspace; insufficient alone for lasting duplicates | Observe visibility parity at counter activation, first particle tick, and the next inactive foreground erase |
| 2 | Completion occurs while the ordinary visibility bit is still one, then overwrites the old render snapshot | High consequence; low confidence that normal scheduling reaches it | Would explain a stranded sprite while logic follows the restored real ship | Break only at the side-specific completion entry and inspect the visibility bit and previous-rendered state |
| 3 | Round-end foreground animation races an active timer hyperspace effect in the shared 90-entry arrays | High | Strong code defect but weak report match without a round transition | Test only if a sighting correlates with death/score transition, or later as a separate bounded case |
| 4 | Simultaneous CPU hyperspace leaves both old ordinary sprites visible for one foreground iteration | High | Could contribute to CPU-versus-CPU blip; does not explain the human-versus-right report if only right hyperspaced | Record both counters and visibility bits at entry |
| 5 | Lead helper changes foreground/timer phasing and exposes an original timing window | Medium | Common to both edited builds and consistent with absence of an original sighting so far | Compare matched original and edited completion checks before attributing causality |
| 6 | Lead patch directly corrupts hyperspace or render state | Low | Would fit edited-only sightings, but owned ranges and writes do not support it | No broad trace; revisit only if a patched completion differs with identical pre-state |
| 7 | Planet renderer or collision interaction | Low | Both sightings had planet disabled and were away from its location | Keep planet disabled in the first matched control |

## Narrow runtime handoff

The audit does not justify heavy state capture as the first runtime action. Use
the existing debugger workflow for these bounded checks:

1. Rehearse the right-side lifecycle on an original-based run copy. At
   `CS:07B6`, immediately after counter activation, record `DS:0061`, `0E2C`,
   `0E4C`, `0CCC`, `0D6C`, and `0D8C`. The expected transient state is counter
   one, dirty zero, entity zero, and visibility commonly still one.
2. Establish whether the first right timer movement at `CS:267F` can occur
   before the next foreground inactive-erase call at `CS:0162`. This is an
   ordering observation, not a long instruction trace.
3. In a separate minimally perturbed run, break only at right completion
   `CS:2732`. The critical invariant is `DS:0CCC == 0` before completion replaces
   the render snapshot. Repeat at left completion `CS:2630` only if needed.
4. Compare the same completion invariant on the exact lead-only and expanded
   gravity-aware builds. Record build hashes and options, but do not dump the
   full data segment unless a completion stop finds a nonzero visibility bit or
   inconsistent snapshot.
5. If completion always sees zero, treat the stranded-sprite sequence as
   unobserved and move next to a locally captured entry window. Broad circular
   logging remains a later fallback.

These checks target the exact static ambiguity and should produce only a few
register/data rows per hyperspace event.
