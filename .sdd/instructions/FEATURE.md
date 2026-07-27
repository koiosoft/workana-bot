## Current Objective
Implement new features for the Agent Instructor to support the initialization of protocol directories, the removal of a deprecated flag, and the addition of new command-line options for copying protocol and PI-related files.

## Key Artifacts (to focus on)
- **Files**:
  - `.sdd/instructions/FEATURE.md` (this file)
  - `instructor.py`
  - `.sdd/protocols/MCP.md`
  - `.sdd/protocols/mcp/disabled/.gitkeep`
  - `.sdd/protocols/mcp/enabled/.gitkeep`
  - `.pi/` (directory to be copied)
  - `config.json`
- **Classes/Interfaces**: None (script-based functionality)
- **Configuration**: `config.json` (for RAG parameters, though not directly involved in this feature)

## Task List
- [x] Read the existing `instructor.py` file to understand the current command-line argument parsing logic, then modify the `main()` function to remove the `--test` argument and add new arguments `--init`, `--pi-commands`, and `--enabled-mcp` with appropriate help messages and functionality.
- [x] Copy the .sdd/protocols/MCP.md file (with its content) and then create the empty directories .sdd/protocols/mcp/disabled and .sdd/protocols/mcp/enabled (each with its respective .gitkeep file, leaving their content to be generated later), when copying the .sdd folder upon executing the --init argument.
- [x] Create empty directories `.sdd/protocols/mcp/disabled` and `.sdd/protocols/mcp/enabled` inside the destination directory when the `--init` argument is used, and add a `.gitkeep` file in each of them to ensure they are tracked by Git.
- [x] Read the current implementation of the `--init` functionality in `instructor.py`, then modify it to include the copying of the `.sdd/protocols/mcp` directory structure and the `.sdd/protocols/MCP.md` file when the `--init` argument is used.
- [x] Read the `.pi/` directory and its contents, then add a new command-line argument `--pi-commands` to the `instructor.py` script that copies the `.pi/` directory and all its contents into the destination directory when executed.
- [x] Add a new command-line argument `--enabled-mcp` to the `instructor.py` script that allows the user to specify which enabled MCP file (e.g., `CODE_BASE_MEMORY.md`) to copy from `.sdd/protocols/mcp/enabled/` to the destination directory when executed.
- [x] Modify the `instructor.py` script to handle the new command-line arguments `--init`, `--pi-commands`, and `--enabled-mcp` by implementing the logic for copying the respective files and directories to the destination directory.
- [x] Update the `instructor.py` script's help message to reflect the new command-line arguments and their descriptions when the user runs the script with the `--help` flag.

## End Task List