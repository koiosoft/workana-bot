## Current Objective
Resolve the `IsADirectoryError` occurring when the Workana scraper attempts to load the Playwright storage state file (`./state.json`), and implement robust error handling in the Telegram bot to inform the user about session or scraping failures.

## Task List
- [x] **Error in app/scraper/adapters/workana.py:70**
  - **Error:** `IsADirectoryError: [Errno 21] Is a directory: './state.json'`
  - **Context:** The error occurs inside `get_projects` when calling `await browser.new_context(**context_kwargs)`. The log indicates `context_kwargs` includes `storage_state: "./state.json"`. The system interprets `./state.json` as a directory instead of a file, causing Playwright's internal file reader to fail during context creation.
  - **Action Required:**
    1.  Modify the logic immediately before `browser.new_context` to explicitly verify that `self.state_file` is a regular file using `os.path.isfile()` in addition to `os.path.exists()`.
    2.  If the path exists but is not a file (e.g., a directory was created by mistake), log a warning, remove the invalid path, and proceed without loading storage state to force a fresh login.
    3.  Ensure the path is absolute or correctly resolved within the Docker container context, as relative paths like `./` can be ambiguous in containerized environments.
    4.  Verify that any logic responsible for saving the session writes to a valid file path and does not accidentally create a directory structure.

- [x] **Error in app/bots/telegram/handlers.py:142**
  - **Error:** Unhandled exception during `await scraper.get_projects()` causing the bot to fail without notifying the Telegram user.
  - **Context:** The stack trace shows the exception propagating from `workana.py` up to `handlers.py` line 142. Currently, there is no specific `try-except` block around the `scraper.get_projects()` call to catch `IsADirectoryError` or other scraping failures.
  - **Action Required:**
    1.  Wrap the `scraper = ScraperFactory.get_scraper()` and `projects = await scraper.get_projects()` calls in a `try-except` block.
    2.  Catch specific exceptions (e.g., `Exception`, `IsADirectoryError`) and log the full error using `logger.error`.
    3.  Before scraping, add a check for `os.path.isfile(scraper.state_file)`. If false, send a targeted message: "⚠️ Archivo de sesión (state.json) no encontrado. Ejecuta `scripts/extract_session.py` para generar un nuevo estado de usuario." and return early.
    4.  Inside the `except` block, send a clear, user-friendly message to the Telegram user (e.g., "⚠️ Error al buscar proyectos: Hubo un problema con la sesión de navegación. Intenta nuevamente o verifica el estado del scraper.").
    5.  Ensure the function returns gracefully after sending messages.

- [x] **Error in app/scraper/adapters/workana.py:Initialization**
  - **Error:** Potential session persistence failure due to relative path `./state.json`.
  - **Context:** The `__init__` method sets `self.state_file = "./state.json"`. In a Docker container, the current working directory might not be the expected volume mount point, leading to path resolution issues or accidental directory creation.
  - **Action Required:**
    1.  Update the `state_file` path initialization to use an absolute path based on the project root or a dedicated configuration variable (e.g., `os.getenv("STATE_FILE_PATH", "/app/state.json")`).
    2.  Ensure the directory where `state_file` is stored exists and is writable by the application user.
    3.  Add a check to ensure that if `state_file` does not exist, the scraper initializes a fresh context without raising an error, and ensures `storage_state` is passed correctly when saving the session after a successful login.