---
description: SDD compiled interaction mode — TERMINAL (default). Reads the active mode, reports the transition, and switches gates to the terminal prompt.
category: SDD
---

# SDD compiled interaction mode — TERMINAL (default)

Switch the session interaction mode to **terminal**. This is the **default** mode: a cycle
started without switching prompts begins in `terminal`.

## Steps

1. **Read** the active mode from `.sdd/interaction-mode.yaml` → `mode`.
2. **Record the transition before acting**, so it is always traceable. Append to
   `.sdd/interaction-mode.yaml` → `history`:
   ```yaml
   - { from: <previous mode>, to: terminal, at: <ISO-8601 timestamp> }
   ```
3. **Set** `mode: terminal` in `.sdd/interaction-mode.yaml`.
4. **Report the transition** to the user, in one line:
   ```
   Interaction mode: <previous mode> -> terminal
   ```
   If the previous mode was already `terminal`, say so and do nothing else.

## Effect

- Every `gate:` is delivered through the **terminal** (native blocking prompt).
- The gate contract is unchanged: it **blocks** until an explicit answer, and is never
  satisfied by inference, a later unrelated message, or a timeout
  (`.sdd/sdd-lang.md` §6.6). If no valid answer arrives, the run stays `blocked` and waits.
- `notify:` steps are non-blocking and behave the same in both modes.

## When to use it

Run on return to the workstation, to switch back from Telegram mode.
