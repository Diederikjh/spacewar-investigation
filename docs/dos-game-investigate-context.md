# Investigate an Old DOS Game: Practical Investigation Guide

Your DOSBox idea is useful, but the best results come from combining **static analysis** of the executable with **targeted dynamic tracing**. A complete instruction trace by itself is usually enormous and does not reveal the original design very clearly.

You can often reconstruct:

- The program’s major subsystems and call graph.
- Its main loop or state machine.
- Input, rendering, audio, file-loading and save-game logic.
- Important structures, tables and resource formats.
- The likely compiler, memory model and runtime library.
- Reasonably readable pseudocode for important routines.

You generally cannot recover the original variable names, comments, source-file structure or exact C/C++ source unless debug information survived.

## Recommended tool stack

### 1. Identify exactly what kind of executable it is

An `.EXE` that runs under DOSBox could be several substantially different things:

- A traditional 16-bit real-mode **MZ executable**.
- A `.COM`-style 16-bit program despite its filename.
- A 16-bit protected-mode program using a DOS extender.
- A 32-bit protected-mode DOS program such as a DOS/4GW application.
- A packed executable that expands its real code into memory at runtime.

Ghidra includes loaders for traditional DOS MZ and NE executables. DOS/4GW programs commonly use the LE executable format, meaning they should be analysed as 32-bit protected-mode programs rather than ordinary 16-bit DOS code.

A useful first pass on Linux, macOS or Windows through WSL is:

```bash
mkdir analysis
cp GAME.EXE analysis/
cd analysis

sha256sum GAME.EXE
file GAME.EXE
xxd -l 128 GAME.EXE
strings -a -n 4 GAME.EXE > strings.txt
```

Then run **Detect It Easy** against it. It recognises DOS MZ, COM and LE/LX formats and can heuristically identify packers and compiler signatures.

```bash
diec GAME.EXE
```

Radare2 can provide another view of the headers, strings and mapped regions:

```bash
rabin2 -I GAME.EXE
rabin2 -H GAME.EXE
rabin2 -S GAME.EXE
rabin2 -z GAME.EXE
```

Also inspect the whole game directory. Companion `.DAT`, `.LIB`, `.OVL`, `.RES`, `.MAP`, `.SYM` and driver files can be more informative than the main executable.

## 2. Load it into Ghidra

Ghidra provides disassembly, decompilation, graphing, scripting and executable loaders, including an old-style DOS MZ loader.

For a normal MZ program, start with:

```text
Format: Old-style DOS Executable (MZ)
Language: x86:LE:16:Real Mode:default
```

For a genuine COM program, import it as a raw binary using 16-bit x86 real mode and map the program at offset `0x100`; that is where DOS loads COM program code.

For LE/LX or a DOS-extender application, use the detected protected-mode format and 32-bit x86 where appropriate.

Be aware that 16-bit segmented programs are harder for decompilers than modern flat-address programs. Ghidra can analyse them, but segment assumptions, far pointers and data-segment references sometimes require manual correction.

### What to do inside Ghidra

Start by locating:

1. The executable entry point.
2. Runtime/compiler initialization.
3. The first large application routine after initialization.
4. DOS and BIOS interrupt calls.
5. Direct hardware access using `IN` and `OUT`.
6. References to text strings, filenames and resource names.
7. Large indirect jump tables, which often represent menus or state machines.
8. Tight loops that access video memory or perform sprite copying.

Rename functions as you discover their role:

```text
program_entry
runtime_initialise
load_configuration
load_resources
menu_loop
game_loop
read_input
update_world
render_frame
play_sound
save_game
shutdown
```

The names may initially be guesses. Rename them again as evidence accumulates.

## 3. Use DOSBox-X rather than ordinary DOSBox for debugging

DOSBox-X has a built-in debugger that can launch a program and break at its entry point:

```dos
DEBUGBOX GAME.EXE
```

Its debugger displays registers, segment registers, memory and disassembly. It supports stepping, real- and protected-mode breakpoints, interrupt breakpoints, memory dumps and bounded CPU-state logging.

Useful commands include:

```text
BP segment offset
BPM selector offset
BPINT interrupt
BPINT interrupt AH-value
BPLIST
BPDEL number

RUN
RUNWATCH

LOGC count
LOGS count
LOGL count

MEMDUMP segment offset count
MEMDUMPBIN segment offset count
```

For example:

```dos
DEBUGBOX GAME.EXE
```

At the entry point:

```text
LOGS 1000
```

The count is hexadecimal, so that records `0x1000` instructions. For a lighter control-flow-oriented trace:

```text
LOGC 4000
```

DOSBox-X writes these CPU traces to `LOGCPU.TXT`. Its debugger also provides `MEMDUMPBIN` for dumping live memory, which is particularly valuable when the executable is packed or self-modifying.

### Target interrupts rather than tracing everything

Useful boundaries to investigate include:

```text
INT 21h    DOS services: files, memory, process services
INT 10h    BIOS video services
INT 16h    BIOS keyboard services
INT 33h    mouse services
INT 1Ah    timing and clock services
```

For example:

```text
BPINT 21
BPINT 10
BPINT 16
BPINT 33
RUN
```

Breaking on every DOS call can become noisy. Once you know which service values matter, use DOSBox-X’s second `BPINT` argument to restrict an interrupt breakpoint to a particular `AH` value.

## 4. Enable subsystem logging

DOSBox-X can log categories such as DOS calls, file I/O, execution, VGA, BIOS, keyboard, mouse, Sound Blaster and CPU activity. Its configuration includes `int21` and `fileio` switches.

A starting configuration might be:

```ini
[log]
logfile = game-analysis.log
int21 = true
fileio = true
exec = true
int10 = true
keyboard = true
mouse = true
sblaster = true
```

Do not enable every category simultaneously at first. Start with file and execution logging, then add video, input or audio depending on the subsystem you are studying.

This produces a much more useful behavioural record than one uninterrupted CPU trace:

```text
Program started
Opened CONFIG.DAT
Allocated memory block
Set video mode
Loaded TITLE.PCX
Opened MUSIC.DAT
Entered menu loop
Read keyboard
Loaded LEVEL01.DAT
```

You then correlate each event with the instruction address and locate that address in Ghidra.

## 5. Use controlled experiments

Dynamic analysis becomes much more effective when each run changes only one thing.

Examples:

- Start the game and exit immediately.
- Open one menu and exit.
- Begin a new game without moving.
- Move once.
- Fire once.
- Save once.
- Load once.
- Trigger one sound effect.
- Enter one new level.

For each experiment, record:

- Which files were opened.
- Which interrupts occurred.
- Which routines became active.
- Which regions of memory changed.
- Which strings or filenames were referenced.
- The call stack around the event.

This is essentially differential analysis:

```text
Trace after standing still
minus
Trace after pressing Fire
=
probable input/fire/projectile path
```

A full trace tells you what executed. A controlled difference tells you **why** it executed.

## 6. Detect and handle packing

Signs of a packed executable include:

- Very few readable strings.
- A small entry-point stub with repetitive copy/decompression loops.
- Code that writes extensively into another memory region.
- An eventual far jump into the newly written region.
- Static disassembly that becomes nonsensical shortly after entry.

In that case:

1. Launch with `DEBUGBOX`.
2. Step through the initial stub.
3. Locate the jump from the unpacker to the expanded program.
4. Stop immediately after that jump.
5. Record the active segments and program bounds.
6. Dump the expanded memory with `MEMDUMPBIN`.
7. Import the dump into Ghidra as a raw 16- or 32-bit x86 image at the corresponding runtime address.

This is one of the strongest reasons to combine DOSBox-X and Ghidra.

## 7. Use Bochs when you need a deeper trace

DOSBox-X is convenient for application-level work. Bochs is useful when you need more exhaustive CPU and hardware visibility.

The Bochs internal debugger supports:

- Segment-and-offset breakpoints in real mode.
- Instruction stepping.
- Register and memory inspection.
- Conditional breakpoints.
- Instruction tracing.
- Register tracing.

Because Bochs simulates instructions rather than primarily optimizing for game execution, it offers detailed visibility but is slower and more cumbersome to configure.

Use it only when DOSBox-X cannot answer a specific question, such as:

- Exactly which code writes to a hardware port.
- How an interrupt handler changes state.
- What executes between two memory writes.
- Whether self-modifying code is involved.

## A realistic reconstruction workflow

A good sequence is:

```text
Executable identification
        ↓
Packing/compiler detection
        ↓
Initial Ghidra import
        ↓
DOSBox-X break at entry
        ↓
Identify runtime initialization
        ↓
Find main/menu/game loops
        ↓
Trace one user action at a time
        ↓
Rename functions and structures in Ghidra
        ↓
Document subsystem boundaries
        ↓
Reimplement selected routines or formats
```

The resulting architecture document could look like:

```text
Startup
 ├── Runtime and memory initialization
 ├── Configuration loader
 ├── Graphics initialization
 └── Resource index loader

Frontend
 ├── Title sequence
 ├── Main menu state machine
 └── Saved-game selector

Game
 ├── Fixed-rate timer
 ├── Input collection
 ├── World update
 ├── Collision processing
 ├── Entity update
 └── Rendering

Platform
 ├── DOS file services
 ├── VGA renderer
 ├── Keyboard/mouse adapter
 └── Sound Blaster driver
```

## Core recommendation

Do not ask DOSBox to blindly output all state for an entire game session. Use DOSBox-X to collect **small, event-focused traces**, then use those addresses and state changes to guide the static Ghidra analysis.

## Suggested first milestone for the Codex investigation

1. Copy the executable and all companion files into an isolated analysis directory.
2. Hash the original files and keep them read-only.
3. Identify the executable format, compiler signature and packer status.
4. Create a Ghidra project with the correct processor mode.
5. Launch under DOSBox-X with `DEBUGBOX`.
6. Capture startup file activity and a short entry-point trace.
7. Record findings in an `analysis-notes.md` file.
8. Commit scripts, notes and configuration files, but avoid committing copyrighted game binaries to a public repository.

## Useful project layout

```text
dos-game-analysis/
├── README.md
├── analysis-notes.md
├── hashes.txt
├── config/
│   └── dosbox-x.conf
├── scripts/
│   ├── inventory.sh
│   └── extract-strings.sh
├── traces/
│   └── .gitkeep
├── dumps/
│   └── .gitkeep
└── original/
    └── GAME.EXE
```

Keep `original/`, memory dumps and proprietary game assets out of version control where necessary.
