# Task 8

## Task
Create the Stage 2A prompt template estimate-full.j2 in app/intelligence/prompts/s2-estimation/ that produces a structured technical estimate for mature requirements. [ASSET: ./assets/TASK008_spec.md]

> **MANDATORY — Prepare:** Read EVERY file referenced by `[ASSET: ...]` markers in this file BEFORE starting the task. Asset paths are relative to THIS file's directory (e.g. `./assets/TASKXXX_spec.md` → the `assets/` folder next to this file). Do not begin implementation until you have read them.

## Status
Completed

## Justification

### What was done
Created the Stage 2A prompt template `estimate-full.j2` at `app/intelligence/prompts/s2-estimation/estimate-full.j2`. The template consumes `analysis_json` (the Stage 1 RequirementAnalysis output) and produces a purely technical JSON estimate with milestones and summary. It implements the 270h minimum floor, overhead multiplier (1.25), technical floors, complexity and delivery pace multipliers, and safety margin (15%). No commercial or persuasive text is emitted — the output is a structured JSON payload consumed by Stage 3.

### Why approaches chosen
- Jinja2 templating for direct compatibility with the existing prompt pipeline
- Extracted estimation constants as template variables for configurability
- Requirement-driven formulas: base hours derived from requirement count scaled by complexity and delivery pace
- Milestone distribution algorithm that tiers scope (small/medium/large) and slices requirements across milestones
- Pure JSON output with `tojson` filter to ensure valid serialization without prose

### Tradeoffs or technical debt
- The template generates synthetic task assignments within milestones by distributing requirements evenly — real-world allocation would require domain expertise
- Milestone hours are computed evenly; actual project milestones vary unevenly depending on dependency chains
- The analysis_json schema is assumed; if Stage 1 output changes, the template may need alignment
- No currency localization — hourly rate is hardcoded at $45 USD
