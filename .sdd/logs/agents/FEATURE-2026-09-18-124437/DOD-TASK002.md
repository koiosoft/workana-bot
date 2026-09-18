# TASK002

## Task
Update every Jinja template reference (get_template calls and template_name literals) across the codebase to the new subfolder-prefixed paths. [ASSET: ./assets/TASK002_spec.md]

## ACK Checklist

- [x] ACK003 Every Jinja template reference in the listed files (gemini.py, openrouter.py, factory.py, tests, docs) — including template_name string literals, not only get_template() calls — references the new subfolder-prefixed path
- [x] ACK004 Running the test suite shows no template-not-found errors caused by the rename
- [x] ACK005 docs/CONTRACT_TYPE_FEATURE.md and docs/USAGE_EXAMPLES.md reflect the new paths


## Review: APPROVED

