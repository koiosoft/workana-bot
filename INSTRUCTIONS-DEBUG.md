## Current Objective
Resolve the `ModuleNotFoundError` occurring when executing `scripts/command.py` by ensuring the project root directory is correctly added to the Python system path (`sys.path`), enabling absolute imports from the `app` package consistent with the pattern established in `app/main.py`.

## Task List
- [x] **Error in scripts/command.py:18**
  - **Error:** `ModuleNotFoundError: No module named 'app'`
  - **Context:** The script attempts to import `UsersRepository` from `app.database.users_repository` at line 18. The traceback indicates Python cannot locate the `app` module relative to the execution context of `scripts/command.py`. Unlike `app/main.py`, which explicitly manipulates `sys.path` to include the project root, `scripts/command.py` lacks this configuration, causing the import to fail when the script is executed from the project root.
  - **Action Required:**
    1. Open the file `scripts/command.py` in the code editor.
    2. Navigate to the top of the file, before any existing import statements related to the `app` package.
    3. Import the `sys` module and the `Path` class from the `pathlib` module if they are not already present.
    4. Implement logic to calculate the project root directory by resolving the path of the current script file (`__file__`) and traversing up two directory levels (parent of the parent) to reach the project root.
    5. Insert the calculated project root path string into the `sys.path` list at index 0 to ensure it takes precedence during module resolution.
    6. Ensure this path manipulation code is placed immediately after the `sys` and `pathlib` imports but before the import statement at line 18 (`from app.database.users_repository import UsersRepository`).
    7. Save the changes to `scripts/command.py`.
    8. Re-execute the command `python3 scripts/command.py` from the project root directory to verify that the `app` module is now recognized and the import succeeds.