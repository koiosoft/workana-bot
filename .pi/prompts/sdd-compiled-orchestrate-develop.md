---
description: Yaml Compiled Generic orchestrator for development SDD protocols (FEATURE, DEBUG) using sub-agents and interactive menus, including automated unit testing (and optional integration testing) with self-correction cycles.
category: SDD
---

We are starting a new development cycle.

To do so, follow the instructions on `.sdd/compiled/agents/orchestrator/dev-orchestrator.yaml`

## Scope — how much you may read

Before the cycle is open, and to resolve the protocol, you may read **only**:

1. The compiled orchestrator and the modules it needs to run the current phase.
2. `.sdd/instructions/<protocol>.md` — the instruction file (read only after the gate resolves the protocol, not before).
3. The cycle LOG directory once `workflow open` has created it.
4. Strictly ignore files in .sdd/inputs.

**Do not recon the project.** The orchestrator coordinates; it does not investigate. Reading the
source tree, git history, specs, or unrelated configuration is out of scope and burns the cycle's
budget before any work starts.

Specifically, before the first dispatch do **not**:
- walk the repository (`find lib/`, `ls` of feature trees, `git log` / `git diff` / `git show`);
- read source files, specs, or `.sdd/config.json` to "understand the project";
- re-read this prompt, the protocol sources, or the sub-agent definitions you were already given.

The context you need for the work arrives **inside the tasks**, not from a survey of the
repository. The workers inspect the code; the orchestrator dispatches and tracks.

## Warning: 
If it asks you to use it, remember that agent-instructor is accessible in the shell since it is a CLI tool.
