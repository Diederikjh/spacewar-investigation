# Spacewar1985 Code-Design Investigation

This repository documents an investigation of the 1985 DOS game `Spacewar1985.exe`, with the goal of understanding its code structure and major subsystems.

The game executable is deliberately excluded from version control. To reproduce the local analysis, place a copy at:

```text
artefact/Spacewar1985.exe
```

The expected SHA-256 hash is:

```text
2fe23087c3d98dfd94e665250cb3c944fb0e210490ead5ec8849dfb0aaf3a490
```

Run the Phase 1 inventory with:

```bash
bash analysis/scripts/phase1-inventory.sh
```

Start with the following documents:

- [Investigation plan](analysis/investigation-plan.md)
- [Potential edits ledger](analysis/potential-edits.md)
- [Phase 1 findings](analysis/phase-1-findings.md)
- [General DOS investigation context](docs/dos-game-investigate-context.md)

Runtime traces, memory dumps, emulator logs, local Ghidra projects, and working copies of the executable are excluded from version control.
