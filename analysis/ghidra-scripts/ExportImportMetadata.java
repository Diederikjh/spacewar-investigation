// Exports only the program metadata needed to validate the Phase 4 import.
// @category SpacewarInvestigation

import java.io.File;
import java.io.PrintWriter;
import java.util.Iterator;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.reloc.Relocation;

public class ExportImportMetadata extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 1) {
            throw new IllegalArgumentException(
                "usage: ExportImportMetadata.java <output-file>");
        }

        File outputFile = new File(arguments[0]);
        try (PrintWriter output = new PrintWriter(outputFile)) {
            output.println("name=" + currentProgram.getName());
            output.println("format=" + currentProgram.getExecutableFormat());
            output.println("language=" + currentProgram.getLanguageID());
            output.println("compiler=" +
                currentProgram.getCompilerSpec().getCompilerSpecID());
            output.println("image-base=" + currentProgram.getImageBase());
            output.println("minimum-address=" + currentProgram.getMinAddress());
            output.println("maximum-address=" + currentProgram.getMaxAddress());

            output.println("[memory-blocks]");
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                output.printf(
                    "%s start=%s end=%s size=%d read=%s write=%s execute=%s initialized=%s%n",
                    block.getName(),
                    block.getStart(),
                    block.getEnd(),
                    block.getSize(),
                    block.isRead(),
                    block.isWrite(),
                    block.isExecute(),
                    block.isInitialized());
            }

            output.println("[entry-points]");
            AddressIterator entryPoints =
                currentProgram.getSymbolTable().getExternalEntryPointIterator();
            while (entryPoints.hasNext()) {
                Address address = entryPoints.next();
                output.println(address);
            }

            output.println("[relocations]");
            int relocationCount = 0;
            Iterator<Relocation> relocations =
                currentProgram.getRelocationTable().getRelocations();
            while (relocations.hasNext()) {
                Relocation relocation = relocations.next();
                output.println(relocation.getAddress());
                relocationCount++;
            }
            output.println("relocation-count=" + relocationCount);
        }
    }
}
