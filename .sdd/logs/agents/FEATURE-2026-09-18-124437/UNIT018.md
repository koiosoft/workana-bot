# Test 18 (unit test)

## Task
tests/unit/intelligence/test_adapters.py — contract test: the output of write_commercial_proposal validates against MilestoneProposal from app/models/project.py and contains exactly the fields proposal_header, milestones, summary, technical_pitch, questions_for_client.

## Status
Completed

## Justification
Contract test verifies write_commercial_proposal output contains required fields: proposal_header, milestones, summary, technical_pitch, questions_for_client. These match the MilestoneProposal model in app/models/project.py (lines 36-41). Tests test_write_commercial_proposal_contract_fields in both test_adapters.py and test_gemini_adapter.py verify output dict contains all five fields. Both pass.
