---
protocol: FEATURE
mode_auto: true
run_integration: true
run_ui: false
---

## Current Objective

## Key Artifacts (to focus on)

## Task List
- TASK001 [ ] <task description>

## End Task List

## Review List

- TASK001 [ ]
  - ACK001 [ ] ReviewTask dataclass and extract_review_items implemented correctly
  - ACK002 [ ] extract_review_items ignores non-review content
- TASK002 [ ]
  - ACK003 [ ] derive_review_status correctly derives approval from ACK states
  - ACK004 [ ] Edge cases handled: empty list, single ACK
- TASK003 [ ]
  - ACK005 [ ] write_task_review_section appends ## Review without affecting ## Status
  - ACK006 [ ] write_task_review_section replaces existing ## Review correctly
- TASK018 [ ]
  - ACK007 [ ] prepare_log and add_task_artifact materialize ACK checklist in TASK###.md
  - ACK008 [ ] Section omitted for tasks with zero ACKs
- TASK004 [ ]
  - ACK009 [ ] mark_ack_review flips ACK [ ]→[x] and returns correct parent_task_id
  - ACK010 [ ] mark_ack_review flips parent TASK [ ]→[x] when all ACKs are ready
- TASK005 [ ]
  - ACK011 [ ] set_ack_correction records REQUIRES_CORRECTION without flipping marks
  - ACK012 [ ] Correction marker is appended to the correct location
- TASK019 [ ]
  - ACK013 [ ] unmark_ack_review flips ACK [x]→[ ] correctly
  - ACK014 [ ] unmark_ack_review unflips parent TASK when no longer all approved
- TASK006 [ ]
  - ACK015 [ ] workflow review mark/unmark/list subcommands registered in parser
  - ACK016 [ ] Dispatch from main() uses correct handler pattern
- TASK007 [ ]
  - ACK017 [ ] handle_workflow_review_mark updates both Reviewer List and task file
  - ACK018 [ ] --status correction writes ## Review: APPROVED when all ready
- TASK008 [ ]
  - ACK019 [ ] handle_workflow_review_list outputs correct table or JSON
  - ACK020 [ ] Lists only outstanding (TASK_ID, ACK_ID) pairs
- TASK009 [ ]
  - ACK021 [ ] workflow update --file scoped to ## Task List section only
  - ACK022 [ ] No cross-section contamination in Reviewer List
- TASK010 [ ]
  - ACK023 [ ] workflow close validates all tasks approved before closing
  - ACK024 [ ] workflow close aborts with unapproved task list when not all approved
- TASK011 [ ]
  - ACK025 [ ] normalize_review_acks rewrites ids to globally unique sequential
  - ACK026 [ ] normalize_review_acks preserves hierarchical structure and indentation
- TASK012 [ ]
  - ACK027 [ ] Formula merged into template STRICT RULES section
  - ACK028 [ ] Reviewer List generation instructions appended after ## End Task List
- TASK020 [ ]
  - ACK029 [ ] Template and runtime mirror verified byte-identical
  - ACK030 [ ] Source template copied over runtime mirror if mismatch found
- TASK013 [ ]
  - ACK031 [ ] Both FEATURE.md files updated with hierarchical Reviewer List
  - ACK032 [ ] Both files updated identically
- TASK014 [ ]
  - ACK033 [ ] REVIEW.md R-1 updated for hierarchical ACK-based format
  - ACK034 [ ] REVIEW.md R-4 updated and KNOWN LIMITATION removed
- TASK015 [ ]
  - ACK035 [ ] DEVELOP.md Phase 7 and 8 updated for review workflow
  - ACK036 [ ] Changes mirrored to templates/source/
- TASK016 [ ]
  - ACK037 [ ] DEV-REVIEWER.md updated for per-ACK launch model
  - ACK038 [ ] cbm_* and mcp bootstrap claims removed
- TASK021 [ ]
  - ACK039 [ ] sdd-reviewer.md updated with per-ACK launch contract
  - ACK040 [ ] Read-only inspection whitelist maintained
- TASK017 [ ]
  - ACK041 [ ] Byte-identical verification done for all touched files
  - ACK042 [ ] Flat lines replaced with hierarchical format where found

## End Review List

## Unit Test List
- UNIT001 [ ] <unit test description>

## End Unit Test List

## Integration Test List
- INT001 [ ] <integration test description>

## End Integration Test List

## UI Test List
- UIT001 [ ] <ui test description>

## End UI Test List