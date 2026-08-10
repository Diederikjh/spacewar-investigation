# EDIT-GRAV-01 Softened-Gravity Prototype

## Outcome

`EDIT-GRAV-01` now has a size-preserving prototype patcher. It replaces the original linear spring-like field with a softened, distance-dependent central field while retaining the existing planet center, gravity option bit, per-entity call site, and split 16.16 velocity additions.

The replacement is 111 bytes. It fits inside the original 102-byte gravity routine and helper plus nine of the ten adjacent zero bytes. One zero byte remains before the next known routine. The edit does not promote the end-of-file padding, change the MZ-declared size, append a byte, or conflict with the separate code range used by `EDIT-CPU-05`.

Static validation and a bounded debugger run have passed. Extended trajectory,
timing, and all-slot validation remain pending.

## Applying the edit

Run the patcher from the repository root with separate input and output paths:

```bash
analysis/scripts/apply-edit-grav-01.py \
    artefact/Spacewar1985.exe \
    analysis/work/SPACEGRAV.EXE
```

The script accepts only the exact investigated input hash, refuses to overwrite an existing output unless `--force` is given, refuses the same input and output path, and aborts before writing if its code no longer fits the owned 112-byte region. Generated executables remain ignored under `analysis/work/`.

## Prototype calculation

For the signed displacement toward the existing center `(319, 99)`, the replacement uses:

```text
to_planet_x = 319 - x
to_planet_y =  99 - y

approximate_radius = max(abs(to_planet_x), abs(to_planet_y))
                   + floor(min(abs(to_planet_x), abs(to_planet_y)) / 2)

denominator = approximate_radius + 32
scale = floor(262144 / denominator)

acceleration_x = sign(to_planet_x)
               * floor(abs(to_planet_x) * scale / denominator)
acceleration_y = sign(to_planet_y)
               * floor(abs(to_planet_y) * scale / denominator)
```

The two divisions by `denominator` approximate a vector proportional to `to_planet / (radius + softening)^2`. This is not an exact Euclidean inverse-square calculation: the radius is inexpensive and anisotropic, and integer truncation quantizes weak components. It nevertheless changes the important radial behavior. Acceleration peaks around the softened inner radius, falls at long distance, remains directed toward the center, and becomes zero exactly at the center.

`262144` is the prototype strength and `32` is its softening radius. Both are named and guarded constants in the patcher so later tuning is explicit. Ships and projectiles still receive the same calculation, gravity remains independently selectable while the planet is hidden, and the existing planet collision logic is unchanged.

Representative raw low-word acceleration values are:

| Position or radius | New `(X, Y)` | Original `(X, Y)` |
|---|---:|---:|
| Initial left ship `(160, 46)` | `(+885, +295)` | `(+1272, +424)` |
| Initial right ship `(480, 138)` | `(-938, -227)` | `(-1288, -312)` |
| Axis-aligned radius 8 | `(+1310, 0)` | `(+64, 0)` |
| Axis-aligned radius 32 | `(+2048, 0)` | `(+256, 0)` |
| Axis-aligned radius 64 | `(+1820, 0)` | `(+512, 0)` |
| Axis-aligned radius 160 | `(+1137, 0)` | `(+1280, 0)` |
| Far-left border `(8, 99)` | `(+692, 0)` | `(+2488, 0)` |
| Center `(319, 99)` | `(0, 0)` | `(0, 0)` |

These values are still raw additions to the low word of signed 16.16 velocity, so divide them by `65536` to express pixels per timer tick squared.

## Placement and ownership

| Range | Original role | Prototype ownership |
|---|---|---|
| `CS:1E30..1E95` | Gravity routine and component-scaling helper, 102 bytes | Replaced gravity calculation |
| `CS:1E96..1E9E` | Nine zero bytes | Continuation of replacement calculation |
| `CS:1E9F` | One zero byte | Remains zero and unowned |
| `CS:1EA0` onward | Scanline-table routine | Unchanged |

Focused disassembly contains four calls from inside the old gravity routine to its old helper at `CS:1E85`, one timer call into the routine at `CS:1E30`, and no direct control-flow target in `CS:1E96..1E9F`. The replacement removes the internal helper calls and returns at `CS:1E9E`. It preserves `BP` and `DI`, preserves `SI` as the entity-slot selector, and uses five temporary stack words at its deepest point.

The original and prototype files are both `0x5800` bytes. The original MZ size fields remain unchanged, the physical trailing `CS:2AE4..2B4F` padding remains zero and outside the declared image, and the original whole-file word-sum convention is preserved by regenerating only the checksum word.

## Reusable edit tools

Common executable-edit mechanics now live in `analysis/scripts/spacewar_edit.py`:

- exact input hash, physical-size, MZ-field, and trailing-padding guards;
- CS-offset to file-offset mapping;
- guarded, non-overlapping byte-region ownership;
- a compact 8086 code builder with resolved short branches and near calls/jumps;
- size and whole-file word-sum preservation;
- SHA-256 reporting; and
- atomic derived-file output with same-path and overwrite guards.

`analysis/scripts/apply-edit-cpu-05.py` now imports those tools. A regenerated EDIT-CPU-05 output is byte-for-byte identical to the previously validated copy, retaining SHA-256 `c96ba303ae45cfbea51719e20e0e8a2ea5bdcc944e5ea633645ef57b968be682`.

The shared layer operates on explicit original-byte ownership regions. Future edits can define their own machine-code and region plans without duplicating MZ validation and output handling. Each current patcher still requires the exact original executable as input; composed edits should be generated as one reviewed plan rather than applied sequentially to already modified outputs.

## Static validation

- The generated gravity code is exactly 111 bytes and leaves `CS:1E9F` zero.
- Disassembly confirms the intended 8086 instructions, short-branch targets, three unsigned divisions, signed direction restoration, 16.16 additions, register restoration, and return at `CS:1E9E`.
- An independent byte comparison found changes only in the checksum word and the owned gravity region.
- The next routine, all later bytes, the MZ size fields, and all 108 physical trailing zero bytes remain unchanged.
- The original and generated whole-file 16-bit word sums are both `FFFF`.
- Exhaustive evaluation of all playable coordinates `X=8..631`, `Y=8..191` proves a nonzero denominator, a 16-bit first quotient, a 32-bit multiplication product, and a signed 16-bit final component.
- The maximum component over those coordinates is `2048`, below the original routine's known maximum absolute component of `2496`.
- The generated ignored copy has SHA-256 `a8be13c10e4440615692b1a4dd580a9569cfc8a6178f7f9f434c0b0ea8bc8d50`.
- Passing an EDIT-CPU-05 output as input is rejected by the exact-original hash guard; the two edits have compatible code placement but are not silently composed.

## Runtime validation

The first bounded debugger run passed. The ignored run copy used an entry-point
`INT 03` only to gain control before startup; the original two entry bytes were
restored in guest memory before execution continued.

| Check | Runtime evidence | Result |
|---|---|---|
| Startup integrity | Execution continued from restored `CS:044C:0000` to the normal animated frontend. | Passed; no startup corruption or illegal-instruction stop |
| Test mode | At the live-game entry, `DS:1076` was `03` and `DS:2040` was `02`. | Both players were computer controlled; gravity was enabled and the planet was hidden |
| Initial left ship | Position `(160, 46)` with both velocity components cleared before one call at `CS:1E30`. | Observed `(+885, +295)`: high/low words `0000:0375`, `0000:0127`; exact model match |
| Initial right ship | The unmodified right slot was processed in the same live timer path. | Observed `(-938, -227)`: high/low words `FFFF:FC56`, `FFFF:FF1D`; exact model match |
| Controlled negative path | The left slot was placed at `(480, 138)` and its velocity was cleared before one call. | Observed `(-938, -227)`, including `FFFF` sign-extension words; exact model match |
| Bounded instruction trace | Each controlled call traversed all three unsigned divisions, restored `BP` and `DI`, and returned to the timer caller. | No divide error, illegal instruction, unhandled interrupt, or stack fault |
| CPU-play stress | The code breakpoints were removed, leaving only the deliberate startup `INT 03` breakpoint. The program then ran for approximately 140 seconds, spanning two CPU-versus-CPU rounds, visible projectile activity, and normal returns to the frontend. | No unexpected debugger stop; final pause was in the ordinary frontend loop |
| Final option state | After the stress interval, `DS:1076` remained `03` and `DS:2040` remained `02`. | Player modes and gravity selection remained intact |

The source executable and generated gravity copy retained their pre-run SHA-256
values. The debugger run copy intentionally had a different hash because its
on-disk entry instruction remained replaced by `INT 03`; restoration occurred
only in guest memory.

This run validates startup, both acceleration sign directions, exact split-word
velocity updates, ordinary CPU-only play, and a small amount of natural
projectile activity. It does not yet prove worst-case timing with all sixteen
entity slots active, test every projectile slot individually, measure missed
timer deadlines or audio timing, or compare bounded trajectories at far,
inner-softening, collision-boundary, and center-adjacent positions. The three
unsigned `DIV` instructions per active entity therefore remain the main timing
risk.

## Remaining decisions

1. Decide whether the prototype strength and softening produce enjoyable trajectories after bounded trajectory testing.
2. Decide whether projectiles should retain exactly the same field as ships.
3. Measure or bound worst-case timer cost with all 16 entity slots active.
4. Test the existing planet-collision boundary and center-adjacent states dynamically.
5. Revalidate any future `EDIT-CPU-06` target-leading design against this specific trajectory model.
