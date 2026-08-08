// Validates Phase 5 computer-player state, constants, and control ordering.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ExportComputerPlayerPolicy extends GhidraScript {
    private record ByteEvidence(String role, boolean code, long address, int[] bytes) {}

    private record TemplateValue(
            String role, long source, long destination, int length, long expected) {}

    private record CallSite(String role, long site, long target) {}

    private static final ByteEvidence[] DECISION_BYTES = {
        new ByteEvidence("robot-mode-image-default", false, 0x1076,
            new int[] { 0x00 }),
        new ByteEvidence("timer-tick-image-default", false, 0x1080,
            new int[] { 0x00 }),
        new ByteEvidence("round-state-copy", true, 0x1f29, new int[] {
            0x8c, 0xd8, 0x8e, 0xc0, 0xbe, 0x50, 0x09, 0xbf,
            0xbc, 0x0c, 0xb9, 0x60, 0x03, 0xfc, 0xf3, 0xa4
        }),
        new ByteEvidence("left-mode-dispatch", true, 0x024f, new int[] {
            0xf6, 0x06, 0x76, 0x10, 0x01, 0x74, 0x03, 0xe9, 0x35, 0x01
        }),
        new ByteEvidence("right-mode-dispatch", true, 0x04a6, new int[] {
            0xf6, 0x06, 0x76, 0x10, 0x02, 0x74, 0x03, 0xe9, 0x35, 0x01
        }),
        new ByteEvidence("left-threat-y-threshold", true, 0x03d3,
            new int[] { 0x3d, 0x60, 0x00 }),
        new ByteEvidence("left-threat-x-threshold", true, 0x03e3,
            new int[] { 0x3d, 0x60, 0x00 }),
        new ByteEvidence("right-close-x-threshold", true, 0x0602,
            new int[] { 0x83, 0xf9, 0x60 }),
        new ByteEvidence("right-close-y-threshold", true, 0x0611,
            new int[] { 0x83, 0xfa, 0x60 }),
        new ByteEvidence("left-aim-commit", true, 0x046c, new int[] {
            0xc6, 0x06, 0x9c, 0x0e, 0x00, 0x8a, 0x1e, 0x5c, 0x0e,
            0x3a, 0xc3, 0x74, 0x08, 0xa2, 0x5c, 0x0e
        }),
        new ByteEvidence("right-aim-commit", true, 0x0677, new int[] {
            0xc6, 0x06, 0xac, 0x0e, 0x00, 0x8a, 0x1e, 0x6c, 0x0e,
            0x3a, 0xc3, 0x74, 0x08, 0xa2, 0x6c, 0x0e
        }),
        new ByteEvidence("left-impulse-threshold", true, 0x0487,
            new int[] { 0x3c, 0x10 }),
        new ByteEvidence("left-hyperspace-mask", true, 0x0497,
            new int[] { 0x25, 0xff, 0x03 }),
        new ByteEvidence("right-impulse-threshold", true, 0x06b3,
            new int[] { 0x3c, 0x10 }),
        new ByteEvidence("right-weapon-threshold", true, 0x06c3,
            new int[] { 0x3c, 0x08 }),
        new ByteEvidence("right-hyperspace-mask", true, 0x06e7,
            new int[] { 0x25, 0xff, 0x03 }),
        new ByteEvidence("angle-x-quarter-turn", true, 0x27b0,
            new int[] { 0x80, 0xc3, 0x40 }),
        new ByteEvidence("angle-component-lookup", true, 0x27b3,
            new int[] { 0x32, 0xff, 0xd1, 0xe3, 0x8b, 0x87, 0x50, 0x20, 0xc3 })
    };

    private static final TemplateValue[] TEMPLATE_VALUES = {
        new TemplateValue("left-x", 0x09b0, 0x0d1c, 2, 0x00a0),
        new TemplateValue("right-x", 0x09c0, 0x0d2c, 2, 0x01e0),
        new TemplateValue("left-y", 0x09d0, 0x0d3c, 2, 0x002e),
        new TemplateValue("right-y", 0x09e0, 0x0d4c, 2, 0x008a),
        new TemplateValue("left-render-dirty", 0x0ab0, 0x0e1c, 1, 0x00),
        new TemplateValue("right-render-dirty", 0x0ac0, 0x0e2c, 1, 0x00),
        new TemplateValue("left-active", 0x0ad0, 0x0e3c, 1, 0x01),
        new TemplateValue("right-active", 0x0ae0, 0x0e4c, 1, 0x01),
        new TemplateValue("left-angle", 0x0af0, 0x0e5c, 1, 0x00),
        new TemplateValue("right-angle", 0x0b00, 0x0e6c, 1, 0x80),
        new TemplateValue("left-rotation-command", 0x0b30, 0x0e9c, 1, 0x00),
        new TemplateValue("right-rotation-command", 0x0b40, 0x0eac, 1, 0x00),
        new TemplateValue("left-action-flags", 0x0b50, 0x0ebc, 1, 0x00),
        new TemplateValue("right-action-flags", 0x0b60, 0x0ecc, 1, 0x00),
        new TemplateValue("left-action-latches", 0x0b70, 0x0edc, 1, 0x00),
        new TemplateValue("right-action-latches", 0x0b80, 0x0eec, 1, 0x00),
        new TemplateValue("left-shield", 0x0b90, 0x0efc, 1, 0x1f),
        new TemplateValue("right-shield", 0x0ba0, 0x0f0c, 1, 0x1f),
        new TemplateValue("left-weapon", 0x0bb0, 0x0f1c, 1, 0x7f),
        new TemplateValue("right-weapon", 0x0bc0, 0x0f2c, 1, 0x7f),
        new TemplateValue("left-phaser-ready", 0x0c10, 0x0f7c, 1, 0xff),
        new TemplateValue("right-phaser-ready", 0x0c20, 0x0f8c, 1, 0xff)
    };

    private static final CallSite[] FOREGROUND_CALLS = {
        new CallSite("left-controls-first", 0x00e4, 0x024f),
        new CallSite("right-controls-second", 0x0158, 0x04a6)
    };

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportComputerPlayerPolicy.java <output-file>");
        }

        try (PrintWriter output = new PrintWriter(new File(arguments[0]))) {
            writeAndValidateBytes(output);
            writeAndValidateTemplate(output);
            writeAndValidateForegroundOrder(output);
        }
    }

    private void writeAndValidateBytes(PrintWriter output) throws Exception {
        output.println("[validated-decision-bytes]");
        for (ByteEvidence evidence : DECISION_BYTES) {
            Address start = evidence.code()
                ? codeAddress(evidence.address())
                : dataAddress(evidence.address());
            assertBytes(start, evidence.bytes(), evidence.role());
            output.printf("%s %s:%04X %s%n",
                evidence.role(),
                evidence.code() ? "12AB" : "1000",
                evidence.address(),
                readHex(start, evidence.bytes().length));
        }
        output.println("validated-decision-byte-ranges=" + DECISION_BYTES.length);
    }

    private void writeAndValidateTemplate(PrintWriter output) throws Exception {
        output.println("[round-template-values]");
        for (TemplateValue value : TEMPLATE_VALUES) {
            if (value.destination() - value.source() != 0x036c) {
                throw new IllegalStateException("template mapping mismatch");
            }
            long actual = readUnsigned(dataAddress(value.source()), value.length());
            if (actual != value.expected()) {
                throw new IllegalStateException(
                    value.role() + " template value mismatch");
            }
            output.printf(
                "%s source=1000:%04X runtime-destination=DS:%04X bytes=%s%n",
                value.role(),
                value.source(),
                value.destination(),
                readHex(dataAddress(value.source()), value.length()));
        }
        output.println("validated-template-values=" + TEMPLATE_VALUES.length);
    }

    private void writeAndValidateForegroundOrder(PrintWriter output)
            throws Exception {
        output.println("[foreground-control-order]");
        for (CallSite call : FOREGROUND_CALLS) {
            Address site = codeAddress(call.site());
            if ((currentProgram.getMemory().getByte(site) & 0xff) != 0xe8) {
                throw new IllegalStateException("expected foreground near call");
            }
            int actual = nearCallTarget(call.site());
            if (actual != call.target()) {
                throw new IllegalStateException("foreground target mismatch");
            }
            output.printf("%s 12AB:%04X -> 12AB:%04X%n",
                call.role(), call.site(), actual);
        }
    }

    private int nearCallTarget(long site) throws Exception {
        Address address = codeAddress(site);
        int low = currentProgram.getMemory().getByte(address.add(1)) & 0xff;
        int high = currentProgram.getMemory().getByte(address.add(2)) & 0xff;
        short displacement = (short) ((high << 8) | low);
        return (int) ((site + 3 + displacement) & 0xffff);
    }

    private long readUnsigned(Address start, int length) throws Exception {
        long value = 0;
        for (int index = 0; index < length; index++) {
            value |= (long) (currentProgram.getMemory().getByte(start.add(index)) & 0xff)
                << (index * 8);
        }
        return value;
    }

    private void assertBytes(Address start, int[] expected, String role)
            throws Exception {
        for (int index = 0; index < expected.length; index++) {
            int actual = currentProgram.getMemory().getByte(start.add(index)) & 0xff;
            if (actual != expected[index]) {
                throw new IllegalStateException(
                    role + " byte mismatch at index " + index);
            }
        }
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
        int count = currentProgram.getMemory().getBytes(start, bytes);
        if (count != length) {
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
