# TASK016

## Task
Update app/bots/telegram/handlers.py to route by contract_type and persist the three collections, keeping the telemetry message format unchanged. [ASSET: ./assets/TASK016_spec.md]

## ACK Checklist

- [x] ACK070 Handler branches by contract_type to the new orchestrator vs the existing generate_proposal
- [x] ACK071 On project_fixed success, a document is inserted into requirement_analyses, one into technical_estimates, and one into proposal_versions; the proposal_versions.proposal_data is the flat MilestoneProposal contract (proposal_header, milestones, summary, technical_pitch, questions_for_client), not the nested accumulated shape
- [x] ACK072 On staff_augmentation, behavior is unchanged
- [x] ACK073 Telemetry message strings keep their current structure (no added/removed fields)
- [x] ACK074 No new external command or response format is introduced to the Telegram bot


## Review: APPROVED

