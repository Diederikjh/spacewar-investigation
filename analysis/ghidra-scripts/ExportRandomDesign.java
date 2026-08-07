// Exports bounded random-generator bytes and validates reviewed direct call sites.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ExportRandomDesign extends GhidraScript {
    private static final long CODE_END = 0x2ae3;

    private record Routine(String role, long start, long end) {}

    private record CallSite(String role, long site, long expectedTarget) {}

    private static final Routine[] ROUTINES = {
        new Routine("random-x-coordinate", 0x28d0, 0x28e0),
        new Routine("random-y-coordinate", 0x28e1, 0x28f1),
        new Routine("next-random", 0x28f2, 0x2915),
        new Routine("seed-from-bios-clock", 0x2916, 0x2931),
        new Routine("draw-random-background", 0x2932, 0x2948)
    };

    private static final CallSite[] CALL_SITES = {
        new CallSite("startup-seed", 0x008a, 0x2916),
        new CallSite("left-robot-choice-1", 0x0484, 0x28f2),
        new CallSite("left-robot-choice-2", 0x0494, 0x28f2),
        new CallSite("right-robot-choice-1", 0x06b0, 0x28f2),
        new CallSite("right-robot-choice-2", 0x06c0, 0x28f2),
        new CallSite("right-robot-choice-3", 0x06e4, 0x28f2),
        new CallSite("left-hyperspace-x", 0x0700, 0x28d0),
        new CallSite("left-hyperspace-y", 0x071b, 0x28e1),
        new CallSite("right-hyperspace-x", 0x0763, 0x28d0),
        new CallSite("right-hyperspace-y", 0x077e, 0x28e1),
        new CallSite("round-end-sound", 0x087f, 0x28f2),
        new CallSite("round-end-star-x-velocity", 0x08d3, 0x28f2),
        new CallSite("round-end-star-y-velocity", 0x08da, 0x28f2),
        new CallSite("frontend-background", 0x0956, 0x2932),
        new CallSite("frontend-star-x-velocity", 0x0a48, 0x28f2),
        new CallSite("frontend-star-y-velocity", 0x0a51, 0x28f2),
        new CallSite("game-background", 0x1f3c, 0x2932),
        new CallSite("randomized-speaker-divisor", 0x289a, 0x28f2),
        new CallSite("random-x-source", 0x28d0, 0x28f2),
        new CallSite("random-y-source", 0x28e1, 0x28f2),
        new CallSite("background-x", 0x2939, 0x28d0),
        new CallSite("background-y", 0x293e, 0x28e1)
    };

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportRandomDesign.java <output-file>");
        }

        try (PrintWriter output = new PrintWriter(new File(arguments[0]))) {
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

            output.println("[initial-random-storage]");
            output.printf(
                "1000:2AA0..1000:2AA5 %s%n",
                readHex(dataAddress(0x2aa0), 6));

            output.println("[validated-direct-calls]");
            for (CallSite callSite : CALL_SITES) {
                monitor.checkCancelled();
                validateAndWriteCall(output, callSite);
            }
            output.println("validated-call-count=" + CALL_SITES.length);
            validateCompleteFocusCallList(output);
        }
    }

    private void validateCompleteFocusCallList(PrintWriter output)
            throws Exception {
        int candidateCount = 0;
        for (long site = 0; site <= CODE_END - 2; site++) {
            monitor.checkCancelled();
            Address address = codeAddress(site);
            if ((currentProgram.getMemory().getByte(address) & 0xff) != 0xe8) {
                continue;
            }

            int low = currentProgram.getMemory().getByte(address.add(1)) & 0xff;
            int high = currentProgram.getMemory().getByte(address.add(2)) & 0xff;
            short displacement = (short) ((high << 8) | low);
            long target = (site + 3 + displacement) & 0xffff;
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

    private boolean isFocusTarget(long target) {
        return target == 0x28d0 || target == 0x28e1 || target == 0x28f2 ||
            target == 0x2916 || target == 0x2932;
    }

    private boolean isReviewedCall(long site, long target) {
        for (CallSite callSite : CALL_SITES) {
            if (callSite.site() == site && callSite.expectedTarget() == target) {
                return true;
            }
        }
        return false;
    }

    private void validateAndWriteCall(PrintWriter output, CallSite callSite)
            throws Exception {
        Address site = codeAddress(callSite.site());
        int opcode = currentProgram.getMemory().getByte(site) & 0xff;
        if (opcode != 0xe8) {
            throw new IllegalStateException(String.format(
                "expected near-call opcode at 12AB:%04X", callSite.site()));
        }

        int low = currentProgram.getMemory().getByte(site.add(1)) & 0xff;
        int high = currentProgram.getMemory().getByte(site.add(2)) & 0xff;
        short displacement = (short) ((high << 8) | low);
        long actualTarget = (callSite.site() + 3 + displacement) & 0xffff;
        if (actualTarget != callSite.expectedTarget()) {
            throw new IllegalStateException(String.format(
                "call target mismatch at 12AB:%04X", callSite.site()));
        }

        output.printf(
            "%s 12AB:%04X -> 12AB:%04X%n",
            callSite.role(),
            callSite.site(),
            actualTarget);
    }

    private Address codeAddress(long offset) {
        Address address = currentProgram.getAddressFactory().getAddress(
            String.format("12ab:%04x", offset));
        if (address == null || !currentProgram.getMemory().contains(address)) {
            throw new IllegalStateException(String.format(
                "code address not mapped: 12AB:%04X", offset));
        }
        return address;
    }

    private Address dataAddress(long offset) {
        Address address = currentProgram.getAddressFactory().getAddress(
            String.format("1000:%04x", offset));
        if (address == null || !currentProgram.getMemory().contains(address)) {
            throw new IllegalStateException(String.format(
                "data address not mapped: 1000:%04X", offset));
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
