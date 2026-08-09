# EDIT-CPU-05 Wrapped-Aim Prototype

## Outcome

`EDIT-CPU-05` now has a size-preserving prototype patcher. It converts the computer players' raw X/Y target deltas into shortest wrapped deltas before proximity tests and bearing calculation. The patch promotes the executable's existing 108 trailing zero bytes into the declared MZ image; it does not append, insert, or remove any physical file bytes.

The generated ignored run copy reached the normal animated frontend under the debugger build. No obvious MZ load, startup, display, title, score, or option-row corruption was visible. This is a startup smoke result, not yet proof of the changed edge-crossing behavior during play.

## Applying the patch

Run the patcher from the repository root with separate input and output paths:

```bash
analysis/scripts/apply-edit-cpu-05.py \
    artefact/Spacewar1985.exe \
    analysis/work/SPACEWRAP.EXE
```

The script accepts only the investigated input hash, refuses to overwrite an existing output unless `--force` is given, refuses to use the same path for input and output, and aborts if its helper code exceeds the 108-byte physical padding. The output stays under `analysis/work/` and remains excluded from version control.

## Behavior change

For a target coordinate, origin coordinate, and world extent, the patch implements:

```text
delta = target - origin

if delta > extent / 2:
    delta -= extent
else if delta < -(extent / 2):
    delta += extent
```

X uses extent `640`; Y uses extent `200`. Exact half-world ties retain their original sign, matching the deterministic model in `analysis/scripts/phase5-computer-player-model.py`.

The normalized signed deltas feed:

- the left computer player's `0x60` raw-axis threat acceptance tests;
- the left computer player's bearing calculation;
- the right computer player's two `0x60` close-axis tests; and
- the right computer player's bearing calculation.

No target priority, weapon probability, impulse probability, hyperspace probability, energy rule, or random-value consumption is intentionally changed.

## Placement and hooks

The input file is `0x5800` bytes, while its original MZ header declares only `0x5794` bytes. Changing the final-page byte count from `0x0194` to zero declares the already-present complete 44th page. The page count remains `0x002C`, so the physical file size does not change. The original whole-file 16-bit word-sum convention is preserved through a regenerated checksum field.

| Purpose | Original site | Original bytes replaced | New target or behavior |
|---|---:|---:|---|
| Left threat Y magnitude | `CS:03CF` | 4 | Call `CS:2AE9`, then resume at `CS:03D3` |
| Left threat X magnitude | `CS:03DF` | 4 | Call `CS:2AE4`, then resume at `CS:03E3` |
| Left signed X/Y bearing deltas | `CS:03F2` | 8 | Call `CS:2B32`, replay the displaced Y load/subtract, then resume at `CS:03FA` |
| Right signed X/Y bearing and proximity deltas | `CS:05F1` | 8 | Call `CS:2B3E`, replay the displaced Y load/subtract, then resume at `CS:05F9` |

| Promoted range | Size | Ownership |
|---|---:|---|
| `CS:2AE4..2B06` | 35 bytes | Axis-specific wrapped absolute-magnitude helper |
| `CS:2B07..2B31` | 43 bytes | Shared signed X/Y wrapping helper |
| `CS:2B32..2B3D` | 12 bytes | Left displaced-instruction wrapper |
| `CS:2B3E..2B49` | 12 bytes | Right displaced-instruction wrapper |
| `CS:2B4A..2B4F` | 6 bytes | Still zero and unowned |

All new control transfers are ordinary near calls within the existing code segment. The patch embeds no segment value and adds no relocation entry.

## Static validation

- The original SHA-256, physical size, MZ fields, hook bytes, and all-zero trailing padding are mandatory patcher guards.
- The existing Ghidra import identifies `CS:2AE4..2AF3`, the old minimum-extra paragraph, as uninitialized `DATA` rather than loaded program content.
- Decoded-operand and analysed-reference scans found no direct ownership reference to that old paragraph.
- `analysis/ghidra-scripts/ExportPaddingPromotionAudit.java` provides a reproducible Ghidra reference/symbol audit. Its report has not yet been captured, so the two preceding checks remain the current ownership evidence.
- The emitted helper occupies 102 bytes and leaves six promoted bytes unused. Disassembly confirmed every hook target, return point, replayed instruction, signed comparison, and constant.
- The original and patched physical sizes are both `0x5800` bytes. The patched MZ declaration is also `0x5800` bytes.
- The patched ignored copy has SHA-256 `c96ba303ae45cfbea51719e20e0e8a2ea5bdcc944e5ea633645ef57b968be682`.
- The executable model exhaustively checks all origin/target coordinate pairs for both world extents, including the four half-world boundary directions.

## Debugger smoke result

The generated patched copy was launched with the existing debugger build and normal CGA configuration. It reached the animated frontend with the expected title, random background, planet, version/copyright text, initial scores, and option row. No illegal-instruction stream, premature termination, graphics corruption, or visible startup failure occurred.

The smoke test exercises the expanded MZ load boundary and ordinary startup but does not execute either new computer-player helper. A later bounded gameplay test must enable each computer player and place the ships or a qualifying projectile across an X and Y boundary before `EDIT-CPU-05` can be considered behaviorally validated.

## Remaining validation

1. Capture the dedicated Ghidra padding-ownership audit when the isolated analysis environment is available.
2. Run the left computer player with the right ship just across each world edge and confirm both threat acceptance and the committed bearing.
3. Repeat the left test with the first qualifying right projectile while the right ship is outside the wrapped acceptance square.
4. Run the right computer player across each edge and confirm its bearing and phaser-versus-photon proximity classification.
5. Exercise exact X `+/-320` and Y `+/-100` ties to confirm the documented sign policy.
6. Run both computer players together long enough to observe repeated helper calls, weapons, impulse, hyperspace, and a normal frontend/round transition.
7. Confirm the original executable hash remains unchanged and keep every patched executable ignored.
