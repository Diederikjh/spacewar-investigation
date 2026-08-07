// Exports bounded star/background evidence and validates reviewed direct calls.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Set;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ExportStarDesign extends GhidraScript {
    private static final long CODE_END = 0x2ae3;
    private static final int PARTICLE_COUNT = 90;

    private record Routine(String role, long start, long end) {}

    private record CallSite(String role, long site, long expectedTarget) {}

    private record WordArray(String role, long base) {}

    private static final Routine[] ROUTINES = {
        new Routine("round-end-animation", 0x07fc, 0x08b3),
        new Routine("initialize-round-end-particles", 0x08b4, 0x08e5),
        new Routine("xor-round-end-particles", 0x08e6, 0x08fe),
        new Routine("initialize-frontend-positions", 0x0a1c, 0x0a42),
        new Routine("initialize-frontend-velocities", 0x0a43, 0x0a75),
        new Routine("frontend-delay-wrappers", 0x0a76, 0x0a86),
        new Routine("animate-frontend-particles", 0x0a87, 0x0ad1),
        new Routine("xor-frontend-particle", 0x1cb7, 0x1cd2),
        new Routine("draw-random-background", 0x2932, 0x2948)
    };

    private static final CallSite[] CALL_SITES = {
        new CallSite("round-end-path-1", 0x07d6, 0x07fc),
        new CallSite("round-end-path-2", 0x07f6, 0x07fc),
        new CallSite("round-end-initialize", 0x0801, 0x08b4),
        new CallSite("round-end-initial-draw", 0x0804, 0x08e6),
        new CallSite("round-end-final-erase", 0x08a2, 0x08e6),
        new CallSite("frontend-background", 0x0956, 0x2932),
        new CallSite("frontend-position-initialize-1", 0x095f, 0x0a1c),
        new CallSite("frontend-velocity-initialize", 0x0962, 0x0a43),
        new CallSite("frontend-return-animation", 0x0965, 0x0a87),
        new CallSite("frontend-hold-1", 0x0968, 0x0a79),
        new CallSite("frontend-position-initialize-2", 0x0971, 0x0a1c),
        new CallSite("frontend-hold-2", 0x0974, 0x0a76),
        new CallSite("frontend-hold-3", 0x097d, 0x0a76),
        new CallSite("frontend-hold-4", 0x0986, 0x0a76),
        new CallSite("position-initialize-draw", 0x0a3b, 0x1cb7),
        new CallSite("velocity-initialize-delay", 0x0a5e, 0x0a79),
        new CallSite("velocity-initialize-animation", 0x0a61, 0x0a87),
        new CallSite("delay-wrapper", 0x0a76, 0x0a79),
        new CallSite("animation-erase", 0x0a8f, 0x1cb7),
        new CallSite("animation-draw", 0x0ac4, 0x1cb7),
        new CallSite("game-background", 0x1f3c, 0x2932)
    };

    private static final WordArray[] ARRAYS = {
        new WordArray("glyph-selector", 0x0171),
        new WordArray("initial-x", 0x0225),
        new WordArray("initial-y", 0x02d9),
        new WordArray("current-x-integer", 0x038d),
        new WordArray("current-y-integer", 0x0441),
        new WordArray("current-x-fraction", 0x04f5),
        new WordArray("current-y-fraction", 0x05a9),
        new WordArray("x-velocity", 0x065d),
        new WordArray("y-velocity", 0x0711)
    };

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportStarDesign.java <output-file>");
        }

        try (PrintWriter output = new PrintWriter(new File(arguments[0]))) {
            writeRoutineBytes(output);
            writeArrayLayout(output);
            writeParticleTemplate(output);
            writeGlyphBytes(output);
            writeParticlePreview(output);
            writeAndValidateCalls(output);
        }
    }

    private void writeRoutineBytes(PrintWriter output) throws Exception {
        output.println("[bounded-routine-bytes]");
        for (Routine routine : ROUTINES) {
            monitor.checkCancelled();
            output.printf(
                "%s 12AB:%04X..12AB:%04X %s%n",
                routine.role(),
                routine.start(),
                routine.end(),
                readHex(codeAddress(routine.start()),
                    (int) (routine.end() - routine.start() + 1)));
        }
    }

    private void writeArrayLayout(PrintWriter output) throws Exception {
        output.println("[word-array-layout]");
        for (WordArray array : ARRAYS) {
            monitor.checkCancelled();
            int minimum = 0xffff;
            int maximum = 0;
            int nonzero = 0;
            for (int index = 0; index < PARTICLE_COUNT; index++) {
                int value = readWord(dataAddress(array.base() + index * 2L));
                minimum = Math.min(minimum, value);
                maximum = Math.max(maximum, value);
                if (value != 0) {
                    nonzero++;
                }
            }
            output.printf(
                "%s 1000:%04X count=%d min=%04X max=%04X nonzero=%d%n",
                array.role(),
                array.base(),
                PARTICLE_COUNT,
                minimum,
                maximum,
                nonzero);
        }
    }

    private void writeParticleTemplate(PrintWriter output) throws Exception {
        output.println("[frontend-particle-template]");
        output.println("index glyph-selector initial-x initial-y");
        Set<String> positions = new HashSet<>();
        int[] glyphCounts = new int[5];
        int minimumX = 0xffff;
        int maximumX = 0;
        int minimumY = 0xffff;
        int maximumY = 0;
        for (int index = 0; index < PARTICLE_COUNT; index++) {
            monitor.checkCancelled();
            int glyph = readWord(dataAddress(0x0171 + index * 2L));
            int x = readWord(dataAddress(0x0225 + index * 2L));
            int y = readWord(dataAddress(0x02d9 + index * 2L));
            if (glyph < 0x0e || glyph > 0x12 || x >= 640 || y >= 200) {
                throw new IllegalStateException(
                    "frontend particle template value outside reviewed bounds");
            }
            if (!positions.add(x + "," + y)) {
                throw new IllegalStateException(
                    "duplicate frontend particle template position");
            }
            glyphCounts[glyph - 0x0e]++;
            minimumX = Math.min(minimumX, x);
            maximumX = Math.max(maximumX, x);
            minimumY = Math.min(minimumY, y);
            maximumY = Math.max(maximumY, y);
            output.printf("%02d %04X %04X %04X%n", index, glyph, x, y);
        }
        output.printf(
            "unique-positions=%d x-range=%04X..%04X y-range=%04X..%04X%n",
            positions.size(),
            minimumX,
            maximumX,
            minimumY,
            maximumY);
        for (int index = 0; index < glyphCounts.length; index++) {
            output.printf(
                "glyph-selector=%02X count=%d%n",
                index + 0x0e,
                glyphCounts[index]);
        }
    }

    private void writeGlyphBytes(PrintWriter output) throws Exception {
        output.println("[frontend-particle-glyphs]");
        for (int glyph = 0x0e; glyph <= 0x12; glyph++) {
            long address = 0x22a0 + glyph * 16L;
            output.printf(
                "selector=%02X address=1000:%04X bytes=%s%n",
                glyph,
                address,
                readHex(dataAddress(address), 16));
        }
    }

    private void writeParticlePreview(PrintWriter output) throws Exception {
        boolean[][] pixels = new boolean[40][512];
        for (int index = 0; index < PARTICLE_COUNT; index++) {
            monitor.checkCancelled();
            int glyph = readWord(dataAddress(0x0171 + index * 2L));
            int originX = readWord(dataAddress(0x0225 + index * 2L)) - 64;
            int originY = readWord(dataAddress(0x02d9 + index * 2L)) - 80;
            long glyphAddress = 0x22a0 + glyph * 16L;
            for (int row = 0; row < 8; row++) {
                int bits = readWord(dataAddress(glyphAddress + row * 2L));
                for (int column = 0; column < 16; column++) {
                    if ((bits & (1 << (15 - column))) != 0) {
                        pixels[originY + row][originX + column] = true;
                    }
                }
            }
        }

        output.println("[frontend-particle-preview-4x4-any]");
        for (int blockY = 0; blockY < 10; blockY++) {
            StringBuilder line = new StringBuilder();
            for (int blockX = 0; blockX < 128; blockX++) {
                boolean set = false;
                for (int y = 0; y < 4; y++) {
                    for (int x = 0; x < 4; x++) {
                        set |= pixels[blockY * 4 + y][blockX * 4 + x];
                    }
                }
                line.append(set ? '#' : ' ');
            }
            output.println(line);
        }
    }

    private void writeAndValidateCalls(PrintWriter output) throws Exception {
        output.println("[validated-direct-calls]");
        for (CallSite callSite : CALL_SITES) {
            monitor.checkCancelled();
            validateAndWriteCall(output, callSite);
        }
        output.println("validated-call-count=" + CALL_SITES.length);

        int candidateCount = 0;
        for (long site = 0; site <= CODE_END - 2; site++) {
            monitor.checkCancelled();
            Address address = codeAddress(site);
            if ((currentProgram.getMemory().getByte(address) & 0xff) != 0xe8) {
                continue;
            }

            int target = nearCallTarget(site);
            if (!isFocusTarget(target)) {
                continue;
            }

            candidateCount++;
            if (!isReviewedCall(site, target)) {
                throw new IllegalStateException(String.format(
                    "unreviewed focus-call candidate 12AB:%04X -> 12AB:%04X",
                    site,
                    target));
            }
        }

        if (candidateCount != CALL_SITES.length) {
            throw new IllegalStateException("reviewed focus-call count mismatch");
        }
        output.println("raw-focus-call-candidates=" + candidateCount);
        output.println("reviewed-call-list-complete=true");
    }

    private void validateAndWriteCall(PrintWriter output, CallSite callSite)
            throws Exception {
        Address site = codeAddress(callSite.site());
        if ((currentProgram.getMemory().getByte(site) & 0xff) != 0xe8) {
            throw new IllegalStateException(String.format(
                "expected near-call opcode at 12AB:%04X", callSite.site()));
        }

        int target = nearCallTarget(callSite.site());
        if (target != callSite.expectedTarget()) {
            throw new IllegalStateException(String.format(
                "call target mismatch at 12AB:%04X", callSite.site()));
        }
        output.printf(
            "%s 12AB:%04X -> 12AB:%04X%n",
            callSite.role(),
            callSite.site(),
            target);
    }

    private int nearCallTarget(long site) throws Exception {
        Address address = codeAddress(site);
        int low = currentProgram.getMemory().getByte(address.add(1)) & 0xff;
        int high = currentProgram.getMemory().getByte(address.add(2)) & 0xff;
        short displacement = (short) ((high << 8) | low);
        return (int) ((site + 3 + displacement) & 0xffff);
    }

    private boolean isFocusTarget(long target) {
        return target == 0x07fc || target == 0x08b4 || target == 0x08e6 ||
            target == 0x0a1c || target == 0x0a43 || target == 0x0a76 ||
            target == 0x0a79 || target == 0x0a87 || target == 0x1cb7 ||
            target == 0x2932;
    }

    private boolean isReviewedCall(long site, long target) {
        for (CallSite callSite : CALL_SITES) {
            if (callSite.site() == site && callSite.expectedTarget() == target) {
                return true;
            }
        }
        return false;
    }

    private int readWord(Address address) throws Exception {
        int low = currentProgram.getMemory().getByte(address) & 0xff;
        int high = currentProgram.getMemory().getByte(address.add(1)) & 0xff;
        return (high << 8) | low;
    }

    private Address codeAddress(long offset) {
        return requiredAddress(String.format("12ab:%04x", offset));
    }

    private Address dataAddress(long offset) {
        return requiredAddress(String.format("1000:%04x", offset));
    }

    private Address requiredAddress(String text) {
        Address address = currentProgram.getAddressFactory().getAddress(text);
        if (address == null || !currentProgram.getMemory().contains(address)) {
            throw new IllegalStateException("address not mapped: " + text);
        }
        return address;
    }

    private String readHex(Address start, int length) throws Exception {
        byte[] bytes = new byte[length];
        int byteCount = currentProgram.getMemory().getBytes(start, bytes);
        if (byteCount != length) {
            throw new IllegalStateException("short memory read at " + start);
        }

        StringBuilder result = new StringBuilder();
        for (int index = 0; index < bytes.length; index++) {
            if (index != 0) {
                result.append(' ');
            }
            result.append(String.format("%02x", bytes[index] & 0xff));
        }
        return result.toString();
    }
}
