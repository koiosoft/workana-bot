# Task 10

## Task
Refactor write-proposal.j2 into a 100% commercial-writing prompt that emits the full flat MilestoneProposal contract (proposal_header, milestones, summary, technical_pitch, questions_for_client), carrying milestones and summary verbatim from the technical estimate. [ASSET: ./assets/TASK010_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification
**Justification:** The existing `write-proposal.j2` mixed estimation logic (milestone construction, 270h minimum, technical floors, anti-bias heuristics) with commercial writing. Per Decision #9, estimation logic belongs in `estimate-full.j2`, and `write-proposal.j2` must be a pure commercial-writing prompt. The refactored template removes all estimation rules (milestone construction, `hours_with_overhead` ceilings, subtotal calculations, total_budget math, delivery_time computation) and instead receives `technical_estimate_json` as input — carrying `milestones` and `summary` verbatim to the output. The template now only generates: `proposal_header` (persuasive greeting with `\\n\\n` segmentation), `technical_pitch` (conditional CTA based on requirement density), and `questions_for_client` (clarification questions). The output JSON contract (MilestoneProposal) remains identical in shape: `proposal_header`, `milestones`, `summary`, `technical_pitch`, `questions_for_client`. The `project_payload_json` context remains for density/type evaluation. Maquetation rules (`\\n\\n` segmentation, JSON escaping)segmentation, JSON escaping) are preserved."]}
