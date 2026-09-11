---
description: Finalization protocol — CLI-driven summary, close, and user notification.
category: SDD
---

> **Principle**: finalization is done **via the CLI** (`agent-instructor workflow summary` + `workflow close`). The CLI is the single source of truth for the cycle state. **Do not** read `.sdd/instructions/${PROTOCOL}.md` to count marks or edit `INDEX.md` by hand.

### F-1: Generate Final Summary (CLI)

1. Review the cycle state via the CLI:
   - `agent-instructor workflow summary`
   - (Optional, machine-readable) `agent-instructor workflow summary --json`

2. Confirm every artifact is `Completed`. If any `Incomplete`/`Pending`/`Failed` item remains, fix it (re-run its `workflow update`) **before** continuing.

3. Derive the `finalization-summary.md` artifact (optional) in `${LOG_DIR}` using `write`, **based on the output of `workflow summary`** — do not re-read the instructions file or re-count marks by hand.

4. If `RUN_INTEGRATION == false`, mention that integration was skipped.

#### Implementation (IMPORTANT — avoid role confusion)
- F-1 and F-2 are **lightweight** steps executed directly (CLI + notification). **No sub-agents required**.
- F-1: use `write` (artifact `finalization-summary.md`, derived from `workflow summary`). F-2: use `ask_user` / direct message to the user.
- **Prohibited**: launching `sdd-worker`, `test-writer`, or `planner` for F-1/F-2 — violates the scope of these roles (TW-3b: test-worker focuses on a single test case; F-1/F-2 are not testing).
- If tools are used, prefer `harness: pi` with a lightweight configured model (no providers without an API key).

---

### F-2: Close the Cycle and Notify User

1. **Close the cycle with the CLI** — the single point of control. It verifies all artifacts are `Completed`, stamps a closure date in the `INDEX.md` header, and clears the `ACTIVE_CYCLE` pointer:
   - `agent-instructor workflow close`

   - If `workflow close` aborts (any artifact not `Completed`), fix the incomplete item(s), re-run their `workflow update`, then re-run `workflow close`. Never bypass it by editing `INDEX.md` or deleting `ACTIVE_CYCLE` manually.

2. Use `ask_user` to display the final summary:
   - *"✅ FEATURE Protocol — Complete"*
   - Show the summary table with task status (from `workflow summary`).
   - If tests passed: *"✅ All tests passed."*
   - If tests failed: *"❌ Some tests failed. Check the logs."*

3. **STOP** execution.