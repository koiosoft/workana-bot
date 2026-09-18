# TASK010

## Task
Refactor write-proposal.j2 into a 100% commercial-writing prompt that emits the full flat MilestoneProposal contract (proposal_header, milestones, summary, technical_pitch, questions_for_client), carrying milestones and summary verbatim from the technical estimate. [ASSET: ./assets/TASK010_spec.md]

## ACK Checklist

- [x] ACK042 Template at app/intelligence/prompts/s3-commercial/write-proposal.j2 contains zero instructions to COMPUTE hours, prices, milestones, or subtotals (it may only carry them through verbatim), and explicitly forbids omitting, renaming, restyling or summarizing milestones and summary
- [x] ACK043 Template accepts technical_estimate_json as the sole technical source
- [x] ACK044 Output schema is the full MilestoneProposal contract: proposal_header, milestones, summary, technical_pitch, questions_for_client (milestones and summary carried through verbatim from the technical estimate)
- [x] ACK045 Conditional CTA and \n\n maquetation are preserved
- [x] ACK046 References inside the prompt to numeric generation (270h, floors, milestone construction) are removed
- [x] ACK093 The Stage 3 rendered output validates against MilestoneProposal from app/models/project.py and exposes all six fields required by the Workana dashboard


## Review: APPROVED

