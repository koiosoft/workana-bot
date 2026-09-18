---
description: SDD compiled interaction mode — TELEGRAM. Reads the active mode, reports the transition, and switches gates to Telegram so the user can answer while away from the workstation.
category: SDD
---

# SDD compiled interaction mode — TELEGRAM

Switch the session interaction mode to **telegram**: the user is away from the workstation and
answers through Telegram. Every decision gate must reach them there.

## Steps

1. **Read** the active mode from `.sdd/interaction-mode.yaml` → `mode`.
2. **Record the transition before acting**, so it is always traceable. Append to
   `.sdd/interaction-mode.yaml` → `history`:
   ```yaml
   - { from: <previous mode>, to: telegram, at: <ISO-8601 timestamp> }
   ```
3. **Set** `mode: telegram` in `.sdd/interaction-mode.yaml`.
4. **Report the transition** to the user, through Telegram, in one line:
   ```
   Interaction mode: <previous mode> -> telegram
   ```
   If the previous mode was already `telegram`, say so and do nothing else.

## Effect

- Every `gate:` is delivered through **Telegram** (a message with buttons), **not** through the
  native terminal prompt. The TUI prompt is not answerable from Telegram, so it must not be
  used while this mode is active.
- The gate contract is unchanged:
  - it **blocks** until the user gives an **explicit answer**;
  - a message is **never** treated as consent by inference — not a generic "continue", not a
    previous message, not a cancelled prompt, not a timeout (`.sdd/sdd-lang.md` §6.6);
  - if no explicit answer arrives, the run stays `blocked` and **waits**. Do **not** advance,
    do **not** choose an option on the user's behalf.
- When a gate opens, state what is being decided, the options, and that the run is paused until
  they answer.
- `notify:` steps stay non-blocking and may also be delivered through Telegram.

## Absolute rule

Never resolve a gate, an ambiguity, or a design decision on your own authority while this mode
is active. Detecting and routing is the orchestrator's job; deciding is the arbiter's or the
user's (`.sdd/sdd-lang.md` §6.7). Advancing without an explicit answer can be catastrophic.

## When to use it

Run when leaving the workstation. Run the terminal-mode prompt on return to switch back.
