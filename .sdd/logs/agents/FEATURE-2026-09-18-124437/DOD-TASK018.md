# TASK018

## Task
Consolidate the numeric/commercial split: verify estimate-full.j2 owns all numeric generation and write-proposal.j2 contains zero numeric instructions, fixing any gap. [ASSET: ./assets/TASK018_spec.md]

## ACK Checklist

- [x] ACK080 write-proposal.j2 contains no instructions to derive hours, prices, milestones, subtotals, or technical floors
- [x] ACK081 estimate-full.j2 contains the migrated 270h minimum rule, technical floors, and milestone construction logic
- [x] ACK082 Both templates are internally consistent (Stage 2A produces numbers, Stage 3 only renders them)
- [x] ACK083 The split does not alter the visual output format (\n\n maquetation and CTA preserved)


## Review: APPROVED

