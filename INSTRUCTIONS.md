## Current Objective
Fix the generation and handling of the `state.json` file to ensure it is created as a file and not a directory, and resolve the error related to the missing session file when scraping Workana.

## Key Artifacts (to focus on)
- **Files**: 
  - `app/scraper/adapters/workana.py`
  - `scripts/extract_session.py`
  - `.env.example`
  - `app/scraper/base.py`
- **Classes/Interfaces**: 
  - `WorkanaScraperAdapter`
  - `ScraperPort`
- **Configuration**: 
  - `STATE_FILE_PATH` environment variable
  - `docker-compose.yml` (implicitly)

## Task List
- [x] Read `app/scraper/adapters/workana.py` to understand how the `WorkanaScraperAdapter` handles the `state.json` file, then modify the `_is_logged_in` and `get_projects` methods to ensure that the `state.json` file is created as a file and not a directory, and add a check to ensure the file exists and is valid before attempting to use it.
- [x] Examine `scripts/extract_session.py` and modify it to ensure it correctly generates the `state.json` file as a file, not a directory, by checking the file type and handling any directory conflicts.
- [x] Review the `WorkanaScraperAdapter` in `app/scraper/adapters/workana.py` and update the logic that handles the `state.json` file to include a validation step that checks if the `state.json` is a file and not a directory before attempting to use it, and add error logging if it is a directory.
- [x] Examine `.env.example` and ensure the `STATE_FILE_PATH` environment variable is correctly set to a file path (e.g., `/usr/src/app/state.json`) and not a directory, and add a note in the file to clarify this.
- [x] Review the error message in the logs (`❌ Archivo de sesión no encontrado: /usr/src/app/state.json`) and modify the error handling in `app/scraper/adapters/workana.py` to provide more detailed logging if the `state.json` is not a file or is missing, including a suggestion to check the file path and ensure it is a valid file.
- [x] Ensure that the `WorkanaScraperAdapter` in `app/scraper/adapters/workana.py` correctly initializes and uses the `state.json` file by verifying that the file exists, is a regular file, and has the correct permissions, and update the code to handle any file-related exceptions gracefully.

## End Task List