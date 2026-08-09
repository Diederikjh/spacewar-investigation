// Audits whether the old MZ minimum-allocation paragraph is referenced.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;

public class ExportPaddingPromotionAudit extends GhidraScript {
    private static final int OLD_EXTRA_START = 0x2ae4;
    private static final int OLD_EXTRA_END = 0x2af3;

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportPaddingPromotionAudit.java <output-file>");
        }

        Address start = codeAddress(OLD_EXTRA_START);
        MemoryBlock block = currentProgram.getMemory().getBlock(start);
        if (block == null || block.isInitialized()) {
            throw new IllegalStateException(
                "old minimum-allocation paragraph is not uninitialized memory");
        }
        if (!"DATA".equals(block.getName())) {
            throw new IllegalStateException("unexpected old allocation block name");
        }
        if (!block.getStart().equals(start)
                || !block.getEnd().equals(codeAddress(OLD_EXTRA_END))) {
            throw new IllegalStateException("unexpected old allocation block bounds");
        }

        int references = 0;
        int symbols = 0;
        try (PrintWriter output = new PrintWriter(new File(arguments[0]))) {
            output.println("[old-minimum-allocation-paragraph]");
            output.printf("range=12AB:%04X..12AB:%04X%n",
                OLD_EXTRA_START, OLD_EXTRA_END);
            output.println("initialized=false");

            for (int offset = OLD_EXTRA_START; offset <= OLD_EXTRA_END; offset++) {
                Address address = codeAddress(offset);
                ReferenceIterator iterator =
                    currentProgram.getReferenceManager().getReferencesTo(address);
                while (iterator.hasNext()) {
                    Reference reference = iterator.next();
                    references++;
                    output.printf("reference %s -> %s type=%s%n",
                        reference.getFromAddress(),
                        reference.getToAddress(),
                        reference.getReferenceType());
                }

                Symbol[] addressSymbols =
                    currentProgram.getSymbolTable().getSymbols(address);
                for (Symbol symbol : addressSymbols) {
                    symbols++;
                    output.printf("symbol %s at %s%n",
                        symbol.getName(), address);
                }
            }

            output.println("references=" + references);
            output.println("symbols=" + symbols);
        }

        if (references != 0 || symbols != 0) {
            throw new IllegalStateException(
                "old minimum-allocation paragraph has program ownership evidence");
        }
    }

    private Address codeAddress(long offset) {
        Address address = currentProgram.getAddressFactory().getAddress(
            String.format("12ab:%04x", offset));
        if (address == null || !currentProgram.getMemory().contains(address)) {
            throw new IllegalStateException(
                String.format("address not mapped: 12AB:%04X", offset));
        }
        return address;
    }
}
