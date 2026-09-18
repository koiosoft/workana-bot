# TASK012

## Task
Add app/intelligence/config.py with a get_maturity_threshold() helper that reads MATURITY_THRESHOLD from the environment (default 8) with strict parsing, as the single source for the staged pipeline threshold. [ASSET: ./assets/TASK012_spec.md]

## ACK Checklist

- [x] ACK096 app/intelligence/config.py exists with a get_maturity_threshold() helper returning an int
- [x] ACK097 get_maturity_threshold() reads MATURITY_THRESHOLD with default 8 and raises a clear configuration error when the value is present but not a valid integer


## Review: APPROVED

