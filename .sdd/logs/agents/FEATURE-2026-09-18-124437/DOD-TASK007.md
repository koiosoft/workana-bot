# TASK007

## Task
Create the Stage 1 prompt template analyze-requirement.j2 in app/intelligence/prompts/s2-estimation/ that extracts entities, gaps, and assigns maturity_score. [ASSET: ./assets/TASK007_spec.md]

## ACK Checklist

- [x] ACK026 Template exists at app/intelligence/prompts/s2-estimation/analyze-requirement.j2
- [x] ACK027 Template extends base/base-role.j2
- [x] ACK028 Template accepts full_description and threshold variables
- [x] ACK029 Output instructions explicitly require maturity_score (1-10 int), maturity_reason, entities, gaps, branch
- [x] ACK030 Branch rule (>= threshold → 'full', else → 'discovery') is stated in the prompt instructions


## Review: APPROVED

