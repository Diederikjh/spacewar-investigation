// Exports bounded computer-player evidence and validates reviewed relationships.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ExportComputerPlayerHandoff extends GhidraScript {
    private record Routine(String role, long start, long end) {}

    private record CallSite(String role, long site, long expectedTarget) {}

    private record WordTable(String role, long start, int[] expectedValues) {}

    private static final Routine[] ROUTINES = {
        new Routine("left-controls-and-robot", 0x024f, 0x04a5),
        new Routine("right-controls-and-robot", 0x04a6, 0x06f5),
        new Routine("left-hyperspace", 0x06f6, 0x0758),
        new Routine("right-hyperspace", 0x0759, 0x07fb),
        new Routine("frontend-robot-mode-toggles", 0x1793, 0x17d9)
    };

    private static final WordTable[] ACTION_TABLES = {
        new WordTable("left-release-actions", 0x0285, new int[] {
            0x02a9, 0x02b5, 0x02c1, 0x02e0, 0x02ff,
            0x031a, 0x0348, 0x035b, 0x036e
        }),
        new WordTable("left-press-actions", 0x0297, new int[] {
            0x02aa, 0x02b6, 0x02c2, 0x02e1, 0x0300,
            0x0320, 0x034e, 0x0361, 0x0374
        }),
        new WordTable("right-release-actions", 0x04dc, new int[] {
            0x0500, 0x050c, 0x0518, 0x0537, 0x0556,
            0x0571, 0x059f, 0x05b2, 0x05c5
        }),
        new WordTable("right-press-actions", 0x04ee, new int[] {
            0x0501, 0x050d, 0x0519, 0x0538, 0x0557,
            0x0577, 0x05a5, 0x05b8, 0x05cb
        })
    };

    private static final CallSite[] ROBOT_CALL_SITES = {
        new CallSite("left-balance-shield-to-weapon", 0x039b, 0x02e1),
        new CallSite("left-balance-weapon-to-shield", 0x03a1, 0x02c2),
        new CallSite("left-no-energy-impulse-off", 0x03ab, 0x0348),
        new CallSite("left-no-energy-phaser-release", 0x03ae, 0x02ff),
        new CallSite("left-threat-phaser", 0x0481, 0x0300),
        new CallSite("left-random-impulse", 0x0484, 0x28f2),
        new CallSite("left-impulse-on", 0x048b, 0x034e),
        new CallSite("left-impulse-off", 0x0491, 0x0348),
        new CallSite("left-random-hyperspace", 0x0494, 0x28f2),
        new CallSite("left-hyperspace-on", 0x049c, 0x0374),
        new CallSite("left-hyperspace-release", 0x04a2, 0x036e),
        new CallSite("right-balance-shield-to-weapon", 0x0699, 0x0538),
        new CallSite("right-balance-weapon-to-shield", 0x069f, 0x0519),
        new CallSite("right-no-energy-impulse-off", 0x06a9, 0x059f),
        new CallSite("right-no-energy-photon-release", 0x06ac, 0x0571),
        new CallSite("right-random-impulse", 0x06b0, 0x28f2),
        new CallSite("right-impulse-on", 0x06b7, 0x05a5),
        new CallSite("right-impulse-off", 0x06bd, 0x059f),
        new CallSite("right-random-weapon", 0x06c0, 0x28f2),
        new CallSite("right-idle-photon-release", 0x06c7, 0x0571),
        new CallSite("right-idle-phaser-release", 0x06ca, 0x0556),
        new CallSite("right-close-photon-release", 0x06d5, 0x0571),
        new CallSite("right-close-phaser", 0x06d8, 0x0557),
        new CallSite("right-distant-phaser-release", 0x06de, 0x0556),
        new CallSite("right-distant-photon", 0x06e1, 0x0577),
        new CallSite("right-random-hyperspace", 0x06e4, 0x28f2),
        new CallSite("right-hyperspace-on", 0x06ec, 0x05cb),
        new CallSite("right-hyperspace-release", 0x06f2, 0x05c5)
    };

    private static final int[] EXPECTED_ANGLE_THRESHOLDS = {
        0x0000, 0x0324, 0x064a, 0x0971, 0x0c9b, 0x0fc9, 0x12fd, 0x1636,
        0x1976, 0x1cbe, 0x2010, 0x236c, 0x26d4, 0x2a49, 0x2dcc, 0x3160,
        0x3505, 0x38bd, 0x3c8a, 0x406e, 0x446a, 0x4882, 0x4cb8, 0x510d,
        0x5586, 0x5a25, 0x5eee, 0x63e4, 0x690b, 0x6e69, 0x7402, 0x79dd
    };

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportComputerPlayerHandoff.java <output-file>");
        }

        try (PrintWriter output = new PrintWriter(new File(arguments[0]))) {
            writeRoutineBytes(output);
            writeAndValidateModeData(output);
            writeAndValidateActionTables(output);
            writeAndValidateAngleTable(output);
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

    private void writeAndValidateModeData(PrintWriter output) throws Exception {
        output.println("[control-data]");
        assertHex(dataAddress(0x1076), new int[] { 0x00 }, "robot-mode-default");
        assertHex(dataAddress(0x1220), new int[] {
            0x20, 0x1e, 0x2e, 0x2c, 0x10, 0x12, 0x1f, 0x11, 0x2d
        }, "left-key-scan-table");
        assertHex(dataAddress(0x1229), new int[] {
            0x4d, 0x4b, 0x51, 0x4f, 0x47, 0x49, 0x4c, 0x48, 0x50
        }, "right-key-scan-table");
        output.printf("robot-mode-default 1000:1076 %s%n",
            readHex(dataAddress(0x1076), 1));
        output.printf("left-key-scan-table 1000:1220 %s%n",
            readHex(dataAddress(0x1220), 9));
        output.printf("right-key-scan-table 1000:1229 %s%n",
            readHex(dataAddress(0x1229), 9));
    }

    private void writeAndValidateActionTables(PrintWriter output)
            throws Exception {
        output.println("[action-tables]");
        for (WordTable table : ACTION_TABLES) {
            StringBuilder values = new StringBuilder();
            for (int index = 0; index < table.expectedValues().length; index++) {
                int actual = readWord(codeAddress(table.start() + index * 2L));
                if (actual != table.expectedValues()[index]) {
                    throw new IllegalStateException(String.format(
                        "%s value mismatch at index %d", table.role(), index));
                }
                if (index != 0) {
                    values.append(' ');
                }
                values.append(String.format("%04X", actual));
            }
            output.printf("%s 12AB:%04X %s%n",
                table.role(), table.start(), values);
        }
    }

    private void writeAndValidateAngleTable(PrintWriter output)
            throws Exception {
        output.println("[angle-threshold-table]");
        StringBuilder values = new StringBuilder();
        for (int index = 0; index < EXPECTED_ANGLE_THRESHOLDS.length; index++) {
            int actual = readWord(dataAddress(0x2250 + index * 2L));
            if (actual != EXPECTED_ANGLE_THRESHOLDS[index]) {
                throw new IllegalStateException(
                    "angle threshold mismatch at index " + index);
            }
            if (index != 0) {
                values.append(' ');
            }
            values.append(String.format("%04X", actual));
        }
        output.printf("1000:2250 count=%d %s%n",
            EXPECTED_ANGLE_THRESHOLDS.length, values);
    }

    private void writeAndValidateCalls(PrintWriter output) throws Exception {
        output.println("[validated-robot-direct-calls]");
        for (CallSite callSite : ROBOT_CALL_SITES) {
            monitor.checkCancelled();
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
            output.printf("%s 12AB:%04X -> 12AB:%04X%n",
                callSite.role(), callSite.site(), target);
        }
        output.println("validated-robot-call-count=" + ROBOT_CALL_SITES.length);
        output.println("raw-byte-call-sweep-complete=false");
        output.println("note=instruction alignment was reviewed before selecting call sites");
    }

    private int nearCallTarget(long site) throws Exception {
        Address address = codeAddress(site);
        int low = currentProgram.getMemory().getByte(address.add(1)) & 0xff;
        int high = currentProgram.getMemory().getByte(address.add(2)) & 0xff;
        short displacement = (short) ((high << 8) | low);
        return (int) ((site + 3 + displacement) & 0xffff);
    }

    private void assertHex(Address start, int[] expected, String role)
            throws Exception {
        for (int index = 0; index < expected.length; index++) {
            int actual = currentProgram.getMemory().getByte(start.add(index)) & 0xff;
            if (actual != expected[index]) {
                throw new IllegalStateException(
                    role + " value mismatch at index " + index);
            }
        }
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
