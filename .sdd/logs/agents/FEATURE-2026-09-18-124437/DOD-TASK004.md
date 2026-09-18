# TASK004

## Task
Create Pydantic models for Stage 2 technical estimation output validation in app/models/estimate.py, reusing existing Milestone, Task, and MilestoneProposalSummary from app/models/project.py. [ASSET: ./assets/TASK004_spec.md]

## ACK Checklist

- [x] ACK011 app/models/estimate.py exists with TechnicalEstimateFull and TechnicalEstimateDiscovery classes
- [x] ACK012 TechnicalEstimateFull.estimate_type is the literal 'full' and TechnicalEstimateDiscovery.estimate_type is the literal 'discovery'
- [x] ACK013 Both models reuse Milestone, Task, and MilestoneProposalSummary imported from app.models.project
- [x] ACK014 Valid example data validates successfully for both models; invalid data raises ValidationError
- [x] ACK015 Both models include a model_used (str) field for audit


## Review: APPROVED

