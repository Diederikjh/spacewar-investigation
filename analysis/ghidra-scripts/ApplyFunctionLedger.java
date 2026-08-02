// Applies reviewed high-confidence function-entry labels without automatic analysis.
// @category SpacewarInvestigation

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Namespace;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;

public class ApplyFunctionLedger extends GhidraScript {
    private static final long CODE_SEGMENT_OFFSET = 0x2ab0;

    private record LedgerRow(
        long loadOffset,
        long codeOffset,
        String proposedName,
        String subsystem,
        String confidence,
        String evidence) {}

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 2) {
            throw new IllegalArgumentException(
                "usage: ApplyFunctionLedger.java <ledger.csv> <output-file>");
        }

        List<LedgerRow> rows = readLedger(new File(arguments[0]));
        File outputFile = new File(arguments[1]);
        SymbolTable symbolTable = currentProgram.getSymbolTable();
        Namespace investigation = symbolTable.getOrCreateNameSpace(
            currentProgram.getGlobalNamespace(),
            "investigation",
            SourceType.USER_DEFINED);

        int appliedCount = 0;
        int deferredCount = 0;
        try (PrintWriter output = new PrintWriter(outputFile)) {
            output.println(
                "qualified-name address subsystem confidence primary function-present");

            for (LedgerRow row : rows) {
                monitor.checkCancelled();
                if (!row.confidence().equals("high")) {
                    deferredCount++;
                    continue;
                }

                if (row.loadOffset() != CODE_SEGMENT_OFFSET + row.codeOffset()) {
                    throw new IllegalStateException(
                        "ledger address mismatch for " + row.proposedName());
                }

                String addressText = String.format("12ab:%04x", row.codeOffset());
                Address address = currentProgram.getAddressFactory().getAddress(addressText);
                if (address == null || !currentProgram.getMemory().contains(address)) {
                    throw new IllegalStateException(
                        "program address not found for " + row.proposedName());
                }

                Namespace subsystem = symbolTable.getOrCreateNameSpace(
                    investigation,
                    row.subsystem(),
                    SourceType.USER_DEFINED);
                Symbol symbol = symbolTable.createLabel(
                    address,
                    row.proposedName(),
                    subsystem,
                    SourceType.USER_DEFINED);
                symbol.setPrimary();

                setPlateComment(
                    address,
                    "Investigation-proposed function entry\n" +
                    "Subsystem: " + row.subsystem() + "\n" +
                    "Confidence: " + row.confidence() + "\n" +
                    "Evidence: " + row.evidence());

                Function function =
                    currentProgram.getFunctionManager().getFunctionAt(address);
                output.printf(
                    "%s %s %s %s %s %s%n",
                    symbol.getName(true),
                    address,
                    row.subsystem(),
                    row.confidence(),
                    symbol.isPrimary(),
                    function != null);
                appliedCount++;
            }

            output.println("applied-high-confidence=" + appliedCount);
            output.println("deferred-lower-confidence=" + deferredCount);
        }
    }

    private List<LedgerRow> readLedger(File ledgerFile) throws Exception {
        List<LedgerRow> rows = new ArrayList<>();
        try (BufferedReader input = new BufferedReader(new FileReader(ledgerFile))) {
            String header = input.readLine();
            if (!"load_module_offset,cs_offset,proposed_name,subsystem,confidence,evidence"
                    .equals(header)) {
                throw new IllegalArgumentException("unexpected function-ledger header");
            }

            String line;
            while ((line = input.readLine()) != null) {
                List<String> fields = parseCsvLine(line);
                if (fields.size() != 6) {
                    throw new IllegalArgumentException("unexpected function-ledger row");
                }
                rows.add(new LedgerRow(
                    Long.decode(fields.get(0)),
                    Long.decode(fields.get(1)),
                    fields.get(2),
                    fields.get(3),
                    fields.get(4),
                    fields.get(5)));
            }
        }
        return rows;
    }

    private List<String> parseCsvLine(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean quoted = false;

        for (int index = 0; index < line.length(); index++) {
            char character = line.charAt(index);
            if (character == '"') {
                if (quoted && index + 1 < line.length() &&
                        line.charAt(index + 1) == '"') {
                    field.append('"');
                    index++;
                }
                else {
                    quoted = !quoted;
                }
            }
            else if (character == ',' && !quoted) {
                fields.add(field.toString());
                field.setLength(0);
            }
            else {
                field.append(character);
            }
        }

        if (quoted) {
            throw new IllegalArgumentException("unterminated quoted CSV field");
        }
        fields.add(field.toString());
        return fields;
    }
}
