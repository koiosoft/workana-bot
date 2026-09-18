# TASK017

## Task
Consolidate the maturity-threshold wiring: verify the get_maturity_threshold helper is the single source and the value is persisted on the analysis record. [ASSET: ./assets/TASK017_spec.md]

## ACK Checklist

- [x] ACK076 The parsed int threshold is forwarded to analyze_requirement
- [x] ACK077 The persisted RequirementAnalyses document contains maturity_threshold_used matching the value used
- [x] ACK078 When the env var is unset, the pipeline still runs with threshold 8
- [x] ACK079 When the env var is set to a non-integer, the code raises a clear configuration error rather than silently falling back
- [x] ACK098 get_maturity_threshold is the single source of the threshold and no inline os.getenv('MATURITY_THRESHOLD') read remains in the adapters


## Review: APPROVED

