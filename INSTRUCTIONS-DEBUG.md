## Current Objective
Resolve the `TypeError` preventing the execution of database migration `v20260520_02` by correcting the invalid keyword argument passed to the `ResilientBulkWriter.add_update()` method.

## Task List
- [x] **Error in migrations/scripts/v20260520_02_update_admin_user_name.py:20**
  - **Error:** `TypeError: ResilientBulkWriter.add_update() got an unexpected keyword argument 'query_filter'`
  - **Context:** The migration script attempts to invoke `writer.add_update()` within the `up` method at line 20. The stack trace indicates that the method signature for `ResilientBulkWriter.add_update()` does not accept `query_filter` as a keyword argument, causing the migration engine to abort and trigger a rollback.
  - **Action Required:**
    1.  Open the file `migrations/scripts/v20260520_02_update_admin_user_name.py`.
    2.  Navigate to the `up` method and locate line 20 where `writer.add_update()` is called.
    3.  Identify the `ResilientBulkWriter` class definition (typically located in `migrations/core/writer.py` or `migrations/core/engine.py`) to verify the correct method signature for `add_update`.
    4.  Determine the correct parameter name used for the query filter in the `add_update` method (e.g., `filter`, `query`, or a positional argument).
    5.  Modify line 20 in the migration script to replace the keyword argument `query_filter` with the correct parameter name identified in the previous step.
    6.  Save the changes and re-run the migration command `python3 migrations/main.py --migrate` to verify the fix.