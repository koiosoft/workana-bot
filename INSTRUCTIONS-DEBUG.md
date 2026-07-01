## Current Objective
Resolve the error encountered when attempting to launch the Playwright browser in the `extract_session.py` script due to missing executable files.

## Task List
- [ ] **Error in scripts/extract_session.py:97**
  - **Error:** `playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at /home/rzavala/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome`
  - **Context:** The error occurs when attempting to launch the Chromium browser using Playwright. The executable file is missing, which indicates that the necessary browser binaries have not been downloaded.
  - **Action Required:** 
    1. Identify that the error is caused by a missing Playwright browser binary.
    2. Ensure that Playwright is installed in the environment.
    3. Run the `playwright install` command to download the required browser binaries.
    4. Verify that the command is executed in the correct virtual environment.
    5. Re-run the `extract_session.py` script after the installation is complete to confirm that the error is resolved.