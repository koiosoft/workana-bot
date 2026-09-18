# TASK001

## Task
Move the seven Jinja prompt templates into the new subfolder structure under app/intelligence/prompts/ as a clean cut (no backward-compatible aliases). [ASSET: ./assets/TASK001_spec.md]

## ACK Checklist

- [x] ACK001 All seven templates exist at the new subfolder paths with semantic prefixes (analyze-, estimate-, write-, refine-, evaluate-, format-); the move uses the plain shell `mv` command
- [x] ACK002 No template file remains at the old name or old location
- [x] ACK095 A repository-wide search confirms no bare template reference (e.g. 'evaluation.j2', 'proposal.j2', 'base_role.j2') remains outside the new subfolders


## Review: APPROVED

