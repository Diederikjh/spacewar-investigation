# Phase 1 Findings: Executable Classification

## Result

`Spacewar1985.exe` is a conventional 16-bit DOS MZ executable intended for real-mode x86. The executable does not appear to be packed. Its entry point immediately performs recognizable video, interrupt, timer, and stack initialization rather than running a decompression stub.

Phase 2 should therefore treat it as a segmented 16-bit program, with the load module's base as the data and stack segment and code beginning `0x2AB` paragraphs above that base.

## Identity

| Property | Finding |
|---|---|
| SHA-256 | `2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490` |
| Physical size | 22,528 bytes (`0x5800`) |
| Internal version string | `V1.50` |
| Internal copyright string | `COPYRIGHT 1985 B SEILER.` |
| Companion files | None present |
| Format | DOS MZ executable |
| Execution model | 16-bit segmented real mode |
| Secondary header | None (`e_lfanew` is zero) |
| Packing | Unlikely; high confidence |
| Compiler/runtime | No recognizable runtime or compiler signature; likely assembly-heavy or handwritten assembly, medium confidence |

The original and working-copy hashes match. The original hash was checked again after inventory generation and was unchanged.

## MZ layout

| Field | Value |
|---|---|
| Header size | 512 bytes (`0x200`) |
| Declared executable size | 22,420 bytes (`0x5794`) |
| Load-module size | 21,908 bytes (`0x5594`) |
| Relocation entries | 5 |
| Initial `CS:IP` | `02AB:0000` |
| Entry offset in load module | `0x2AB0` |
| Entry offset in file | `0x2CB0` |
| Header `SS:SP` | `0000:0000` |
| Minimum extra allocation | 1 paragraph (16 bytes) |
| Maximum extra allocation | `0xFFFF` paragraphs |
| Overlay number | 0 |

The 108 bytes after the declared executable size are all zero. They pad the physical file to the next 512-byte boundary and do not look like an overlay or appended payload.

The header's five relocation entries all point into the code segment that begins at `CS=0x02AB`. The early relocated immediates establish the load-module base for `DS` and later `SS`. This is consistent with a deliberate data-before-code layout rather than a flat COM image.

## Packing assessment

Evidence against executable packing:

- The entry point immediately contains coherent application/platform initialization.
- Control flow consists of ordinary calls and branches into later routines, with no copy/decompression loop or jump into newly written memory.
- Whole-file entropy is only 5.3928 bits per byte.
- Zero bytes account for 36.91% of the file.
- There are 136 readable strings of at least four characters, comprising approximately 10.22% of the file.
- Game instructions, menus, labels, version information, and copyright text remain directly readable.
- No common LZEXE, PKLITE, EXEPACK, DIET, UPX, Borland, Microsoft, Watcom, or runtime-error string signature was found.

Conclusion: proceed directly with static disassembly. A runtime unpacking capture is not part of the current path.

## Entry-point behavior

The first instructions provide useful architectural evidence:

1. Preserve the DOS-provided `DS` value in the code segment.
2. Load the relocation-adjusted program base into `DS`.
3. Query the current video mode using BIOS interrupt `10h`, function `0Fh`.
4. Write to display-control port `0x3BF`.
5. Select video memory at segment `B800h` and test its addressing behavior.
6. On failure, restore the video mode and print the embedded graphics-card error with DOS interrupt `21h`, function `09h`.
7. Modify BIOS data-area state at segment `0040h` and write to floppy-controller port `0x3F2`.
8. Save the DOS stack and establish a custom stack at the program's relocated load base with `SP=0x0166`.
9. Program PIT channel 0 through ports `0x43` and `0x40` with divisor `0x4006`, approximately 72.8 Hz from the standard PC timer input.
10. Install a handler at `CS:1F80` into interrupt vector 9, the hardware keyboard interrupt.
11. Call several initialization routines and transfer into the program's frontend/control code.

This startup is tightly coupled to IBM-PC-compatible hardware. The game appears to own keyboard and timer behavior directly instead of relying only on DOS or BIOS polling.

## Preliminary design implications

These are starting hypotheses for Phase 2, not final function identifications:

- **Custom platform layer:** startup, shutdown, video checking, interrupt installation, and timer programming are explicit and compact.
- **Tick-driven design:** PIT reprogramming strongly suggests that simulation, input, or sound is driven from a higher-frequency fixed tick.
- **Interrupt-backed input:** the custom interrupt-9 vector indicates keyboard state is probably collected asynchronously into shared state tables.
- **Direct framebuffer renderer:** use of `B800h` and a 16 KiB addressing test points to direct CGA graphics-memory access.
- **Self-contained assets:** no filenames or external-resource names were found, while UI text and apparent bitmap/table data are embedded in the executable.
- **Assembly-oriented memory layout:** relocated segment constants, a custom stack, direct I/O, and the lack of compiler-runtime scaffolding suggest handwritten or heavily assembly-based code.
- **Table-oriented game state:** the first post-startup code contains repeated indexed operations over nearby global regions. Phase 2 should test whether these are player, projectile, or entity records.

## Confidence and open questions

| Conclusion | Confidence | Remaining work |
|---|---|---|
| Conventional MZ, 16-bit real mode | High | Cross-check with radare2 and later Ghidra import |
| Not packed | High | Confirm that no later self-modifying region appears in full disassembly |
| CGA/direct framebuffer design | High | Identify video mode selection and drawing primitives |
| Custom keyboard ISR | High | Disassemble `CS:1F80` and map its state table |
| Timer-driven simulation or audio | Medium-high | Locate timer-vector installation and follow tick consumers |
| Handwritten/assembly-heavy implementation | Medium | Look for library idioms and compiler fingerprints across all routines |
| All resources embedded | Medium | Inspect DOS interrupt calls for generated or non-string filenames |

## Phase 2 recommendation

Install radare2 and NASM/ndisasm as lightweight native packages, then construct a complete 16-bit disassembly and address map. DOSBox-X can be installed in the same reviewed package transaction, but dynamic execution should wait until the initial static function ledger identifies useful breakpoint addresses.

The first Phase 2 targets should be:

1. The frontend target reached from the startup jump.
2. The handler installed at `CS:1F80` for interrupt 9.
3. The routine that saves or replaces the timer vector.
4. The initialization and shutdown calls around the entry point.
5. Cross-references to the menu and instruction strings.
6. Repeated accesses to candidate player/entity-state tables.

