# TASK008

## Task
Create the Stage 2A prompt template estimate-full.j2 in app/intelligence/prompts/s2-estimation/ that produces a structured technical estimate for mature requirements. [ASSET: ./assets/TASK008_spec.md]

## ACK Checklist

- [x] ACK031 Template exists at app/intelligence/prompts/s2-estimation/estimate-full.j2
- [x] ACK032 Template accepts analysis_json as input
- [x] ACK033 Output schema defines milestones[] with step, name, tasks (description, hours_with_overhead), hours_with_overhead, subtotal
- [x] ACK034 Output schema defines summary with total_hours, total_budget, delivery_time_weeks, hourly_rate_applied
- [x] ACK035 270h minimum rule is preserved as a constraint inside the template
- [x] ACK036 Template instructions explicitly forbid commercial/persuasive language; this is a Stage 2A gatekeeper


## Review: APPROVED

