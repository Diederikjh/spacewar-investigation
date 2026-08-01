# Repository Instructions

## Paths

- Use repository-relative paths in documentation, scripts, reports, examples, logs, and generated artefacts.
- Do not commit absolute workspace paths, home-directory paths, usernames, hostnames, mount points, or expanded `~` paths.
- Run reporting tools from the repository root and pass relative input paths when their output includes filenames.
- Absolute paths may be used transiently when required to locate the repository, but they must not appear in saved or committed output.

## Machine privacy

- Treat information about the analysis machine as private by default.
- It is acceptable to state that the analysis platform is Ubuntu. Do not record the host name, Ubuntu release, kernel version, architecture, user identity, email address, network information, environment variables, or filesystem layout in repository content or generated output.
- Do not commit inventories or versions of installed software, packages, runtimes, shells, emulators, compilers, or analysis tools.
- Project requirements and intentionally selected dependency versions are acceptable when they describe what the project needs rather than what happens to be installed on the machine.
- Keep transient host-inspection results out of repository files and progress logs.
- Treat Git author and committer metadata as public information.
- Use a repository-local pseudonymous author name and noreply email address; never use a personal email address in commits intended for publication.
- Before publishing, audit every reachable commit for personal author or committer metadata, not only the current working tree.

## Terminology

- Describe this work as an investigation or analysis.
- Use terms such as `investigate`, `investigation`, `analyse`, and `analysis` consistently in documentation, reports, commit messages, and generated output.
- Do not substitute terminology that makes the investigation sound invasive or adversarial.

## Human-only document

- `HUMANS.md` is exclusively for human readers.
- Agents must not open, read, search, quote, summarize, index, analyse, diff, or otherwise inspect the contents of `HUMANS.md`.
- Treat `HUMANS.md` as an opaque file. It may be staged or committed when explicitly requested, but its contents must not be displayed or processed.
- Exclude `HUMANS.md` from repository-wide searches, content audits, and automated report generation.

## Public-repository safety

- Do not commit the game executable, working copies, memory dumps, runtime traces, emulator logs, or local analysis project databases.
- Before each commit, audit staged text for absolute paths and machine-specific identifiers, and confirm ignored proprietary artefacts are not staged.
- When a generated report leaks host information, fix its generator and regenerate the report rather than editing only the generated output.
