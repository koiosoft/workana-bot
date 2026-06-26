## Current Objective
- Parse 'Hace casi una hora' as 1 hour and review the error 'No se pudo parsear el tiempo relativo'. Review the method `_calculate_estimated_published_at`.
- Create a script named `command.py` in the `/scripts` folder with three commands:
  a) Create a new User (with input password hidden)
  b) Update user Password with Email (with input password hidden)
  c) Delete projects (All, from date: 2026-10-01, format yyyy-mm-dd)
- Review and fix any issues in the tests.

## Key Artifacts (to focus on)
- **Files**:
  - `app/scraper/adapters/dummy.py`
  - `app/models/project.py`
  - `app/database/users_repository.py`
  - `app/services/auth_service.py`
  - `scripts/command.py` (new file)
  - `tests/unit/api/test_projects.py`
  - `tests/unit/bots/test_telegram_handlers.py`
  - `tests/unit/database/test_users_repository.py`
- **Classes/Interfaces**:
  - `DummyScraperAdapter` (from `app/scraper/adapters/dummy.py`)
  - `Project` (from `app/models/project.py`)
  - `UsersRepository` (from `app/database/users_repository.py`)
  - `AuthService` (from `app/services/auth_service.py`)
- **Configuration**:
  - `AUTH_SECRET` (environment variable)
  - `MONGO_URI` (environment variable)

## Task List
- [x] Read `app/scraper/adapters/dummy.py` to understand how the `fetch_full_detail` method parses relative times. Fix the method to correctly parse 'Hace casi una hora' as 1 hour and resolve the 'No se pudo parsear el tiempo relativo' error.
- [x] Examine `app/database/projects_repository.py` and update the `ProjectsRepository` class to ensure the `_calculate_estimated_published_at` method supports the new relative time parsing logic.
- [x] Read `app/database/users_repository.py` to understand user management methods. Create `scripts/command.py` with a `create_user` command that prompts for a hidden password input and uses `UsersRepository` to create a new user.
- [x] Add an `update_password` command to `scripts/command.py` that prompts for a hidden password input and uses `UsersRepository` to update a user's password via email.
- [x] Add a `delete_projects` command to `scripts/command.py` that deletes all projects or projects from a specified date (format: yyyy-mm-dd) using `ProjectsRepository`.
- [x] Review `tests/unit/api/test_projects.py` and fix test cases for project creation, updating, and deletion, including date-based deletion logic.
- [x] Review `tests/unit/bots/test_telegram_handlers.py` and fix test cases for user creation, password updates, and project deletion commands.
- [x] Review `tests/unit/database/test_users_repository.py` and fix test cases for user creation with hidden password input and password update functionality.
- [x] Add an `prune_projects` command to `scripts/command.py` to delete phisically all projects checked with soft-delete.  Add this command to make file too.
## End Task List