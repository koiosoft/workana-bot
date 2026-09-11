---
description: Finalization step for documentation updates — reports completion and ends the orchestration.
category: SDD
---

### F-1: Report Completion

- Inform the user that all documentation tasks have been processed successfully.
- Provide a brief summary (e.g., number of tasks completed, any notable changes).
- **Do not modify any files** during this step.
- End the orchestration session and return control to the user.

---

### ⚠️ Safety Rules

- **NEVER execute shell commands, run tests, or read source code files directly.**
- **NEVER write or edit source code files directly.** Only `replace_in_file` is permitted on `.sdd/instructions/SPEC_UPDATE.md` (which should already be fully updated by now).
- **If something seems wrong**, use `ask_user` to ask for guidance before ending.