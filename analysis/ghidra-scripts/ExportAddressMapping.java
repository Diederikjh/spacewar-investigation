// Exports known Phase 1/3 locations in Ghidra's segmented address space.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ExportAddressMapping extends GhidraScript {
    private static final long HEADER_SIZE = 0x200;
    private static final long CODE_SEGMENT_OFFSET = 0x2ab0;

    private record KnownPoint(String role, long loadOffset) {}

    private static final KnownPoint[] KNOWN_POINTS = {
        new KnownPoint("random-state", 0x2aa0),
        new KnownPoint("program-entry", 0x2ab0),
        new KnownPoint("game-entry", 0x2b6c),
        new KnownPoint("frontend-entry", 0x33f0),
        new KnownPoint("frontend-timer", 0x41dd),
        new KnownPoint("keyboard-handler", 0x4a30),
        new KnownPoint("game-timer", 0x4ded),
        new KnownPoint("next-random", 0x53a2),
        new KnownPoint("seed-random", 0x53c6),
        new KnownPoint("background-pixels", 0x53e2)
    };

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportAddressMapping.java <output-file>");
        }

        File outputFile = new File(arguments[0]);
        try (PrintWriter output = new PrintWriter(outputFile)) {
            output.println(
                "role load-module file-offset ghidra-address first-eight-bytes");
            for (KnownPoint point : KNOWN_POINTS) {
                String ghidraAddress = toGhidraAddress(point.loadOffset());
                Address address = currentProgram.getAddressFactory()
                    .getAddress(ghidraAddress);
                if (address == null) {
                    throw new IllegalStateException(
                        "address not found: " + ghidraAddress);
                }

                byte[] bytes = new byte[8];
                int byteCount = currentProgram.getMemory().getBytes(address, bytes);
                output.printf(
                    "%s 0x%04x 0x%04x %s %s%n",
                    point.role(),
                    point.loadOffset(),
                    point.loadOffset() + HEADER_SIZE,
                    address,
                    toHex(bytes, byteCount));
            }
        }
    }

    private String toGhidraAddress(long loadOffset) {
        if (loadOffset < CODE_SEGMENT_OFFSET) {
            return String.format("1000:%04x", loadOffset);
        }
        return String.format("12ab:%04x", loadOffset - CODE_SEGMENT_OFFSET);
    }

    private String toHex(byte[] bytes, int byteCount) {
        StringBuilder result = new StringBuilder();
        for (int index = 0; index < byteCount; index++) {
            if (index != 0) {
                result.append(' ');
            }
            result.append(String.format("%02x", bytes[index] & 0xff));
        }
        return result.toString();
    }
}
