# EDIT-HYPER-02 Round-Start Counter-Reset Prototype

## Outcome

`EDIT-HYPER-02` now has a size-preserving prototype patcher. Before a new
round copies and draws its initial ship state, it clears the adjacent left and
right hyperspace counters at `DS:0060/0061`. An effect abandoned through F1 can
therefore no longer resume when the gameplay timer is installed again.

The patch does not grow the executable, promote its physical trailing padding,
change its MZ-declared size, or clear the shared particle arrays. Static
validation and the first controlled runtime regression have passed. The
left-side and right-side F1/F2 reproductions no longer leave inherited particles
or a default-position ghost, and ordinary same-round hyperspace still completes
for both ships.

## Applying the edit

Run the guarded patcher from the repository root:

```bash
analysis/scripts/apply-edit-hyper-02.py \
    artefact/Spacewar1985.exe \
    analysis/work/SPACEHYP.EXE
```

The input must match the exact investigated original. The script refuses the
same input/output path, refuses to replace an output unless `--force` is used,
guards every replaced original byte, and writes the generated executable under
the ignored `analysis/work/` directory.

## Behavior and placement

Original game entry at `CS:00BC` resets the private stack, writes zero to the
pause byte at `DS:0170`, and calls round initialization at `CS:1F29`. The patch
replaces only the five-byte pause write at `CS:00BF..00C3` with a near call and
two NOPs. Its helper performs the displaced pause clear and the new counter
reset:

```text
xor ax, ax
mov [0170h], al       ; original pause reset
mov [0060h], ax       ; left and right hyperspace counters
ret
```

The following call begins by replacing `AX` with `DS`, so returning zero in
`AX` does not change downstream behavior. The F2 transition reaches game entry
from the frontend timer while interrupts are disabled; both counter bytes are
therefore cleared before round state is copied, the initial ships are drawn, or
the gameplay timer is installed.

| Range | Original role | Prototype ownership |
|---|---|---|
| `CS:00BF..00C3` | Five-byte pause clear | Near call to helper plus two NOPs |
| `CS:28B4..28C4` | PC-speaker/state reset routine | Unchanged |
| `CS:28C5..28CD` | Nine internal zero bytes | Pause and hyperspace-counter reset helper |
| `CS:28CE..28CF` | Final two internal zero bytes | Remain zero and unowned |
| `CS:28D0` onward | Random X-coordinate helper | Unchanged |

The internal cave lies between two high-confidence function entries recorded in
the function ledger. It is disjoint from the adjacent gravity cave at
`CS:1E96..1E9F` and the physical-padding area at `CS:2AE4` used by the
computer-player prototypes.

## Static validation

- The original input hash, physical size, MZ fields, checksum convention,
  five-byte hook, and eleven zero cave bytes are exact guards.
- The helper occupies nine bytes and leaves `CS:28CE..28CF` zero.
- The executable remains physically `0x5800` bytes and still declares
  `0x5794` bytes; its original 108 physical trailing zero bytes remain unused.
- The original whole-file 16-bit word sum is preserved through the checksum
  field.
- Byte comparison permits changes only in the checksum word, the five-byte
  hook, and the eleven-byte cave.
- The random X-coordinate helper still begins unchanged at `CS:28D0`.
- Disassembly resolves the hook to `call CS:28C5`, followed by its two NOPs and
  the unchanged `call CS:1F29` round initializer. The helper decodes to the four
  intended instructions and returns at `CS:28CD`.
- `EDIT-GRAV-01`, `EDIT-CPU-05`, and `EDIT-CPU-06` owned code regions do not
  overlap this prototype. Patch composition still requires a separately
  reviewed combined generator rather than sequential patching.
- Regeneration is byte-for-byte deterministic. The ignored prototype has
  SHA-256
  `3c4d99165e9f2600258f492673a54ac2253e69b82479d2e26e5e3e6dc82e1fb5`.

## Runtime validation

The first controlled run used the exact generated prototype identified above:

1. A temporary entry trap stopped cleanly at the executable entry. Restoring
   the original `mov ax,ds` instruction in memory allowed normal startup to the
   frontend without an unexpected debugger stop.
2. In human-versus-human play, left hyperspace was followed immediately by F1,
   then a replacement round was started with F2.
3. A breakpoint at `CS:00C4`, immediately after the new helper and before the
   original `call CS:1F29` initializer, showed `AX=0000` and
   `DS:0060/0061 = 00/00`.
4. The replacement round showed no inherited particles. After repeated left
   impulse input moved the ship away, no sprite remained at its default start.
5. The same timed F1/F2 sequence was repeated with right hyperspace. The new
   round again showed no inherited particles and no default-position ghost
   after right impulse input.
6. One uninterrupted ordinary hyperspace cycle per side completed, with each
   ship reappearing at a new position and no visible rendering corruption.

This establishes the intended round-boundary state change and passes the exact
visual failure sequence on both sides. It does not yet measure ordinary-cycle
duration, energy, or random-call cadence, and it does not replace the broader
validation matrix. Remaining useful checks are delayed F2 restarts,
simultaneous effects, gravity/planet option combinations, natural round endings,
and a bounded circular-trace pilot requiring zero new-round draws with nonzero
counters.

The original executable remains immutable. The generated prototype and all
runtime evidence stay under ignored paths.
