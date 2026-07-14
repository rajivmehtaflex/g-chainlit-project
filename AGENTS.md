# Repository Guidelines

## Project Structure & Module Organization

This repository is a Chainlit assistant with SQLite history and project-aware chat profiles. `main.py` initializes `chainlit.db` from `schema.sql` and wires auth, chat, settings, and project/file callbacks. `projects.py` owns the SQLite project/file repository: creation, description updates, deletion, uploads, renaming, and file deletion. `data_layer.py` extends Chainlit persistence and prefixes project thread names with `[Project] `. Config and translations are in `.chainlit/`; welcome copy is in `chainlit.md`. Static assets are in `public/`, including `custom.css` and `elements/ProjectDashboard.jsx`, `ReloadPrompt.jsx`, and `WelcomeCard.jsx`. Tests are in `tests/`. `ref_ai/` contains reference notes. Runtime paths such as `chainlit.db`, `project_files/`, `.files/`, logs, PID files, `.venv/`, and `__pycache__/` are generated.

Projects are created from the Settings panel (gear icon). The dashboard edits descriptions and supports file rename/delete plus confirmed project deletion. Names remain immutable because thread tags and profile identity are name-keyed. Creating or deleting a project requires a page reload to refresh the profile dropdown and thread list; the app displays `ReloadPrompt` for this.

## Build, Test, and Development Commands

- `uv sync`: install locked Python 3.12 dependencies.
- `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`: run Chainlit directly.
- `./start.sh`: run Chainlit in the background using `CHAINLIT_PORT` from `.env`.
- `./stop.sh`: stop the process started by `start.sh`.
- `uv run pytest`: run the configured test suite.

Use `.env` with `CHAINLIT_AUTH_USERNAME`, `CHAINLIT_AUTH_PASSWORD`, `STATIC_RESPONSE`, and `CHAINLIT_PORT`.

## Coding Style & Naming Conventions

Use Python 3.12, four-space indentation, typed callbacks, small Chainlit functions, `snake_case` Python names, and uppercase underscore environment variables. Keep `schema.sql` explicit and idempotent. Use PascalCase names/exports for custom elements and Chainlit globals such as `props` and `sendUserMessage`.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio`; name files `test_*.py`. Add focused repository tests for new persistence behavior. Manually verify sign-in, new/resumed chats, project switching and `[Project]` prefixes, Settings-panel creation and reload, description editing, file attachment, safe/duplicate-resistant renaming, file deletion, and confirmed project deletion with cascading tagged-thread cleanup.

## Commit & Pull Request Guidelines

Use concise imperative messages such as `Add ReloadPrompt custom element` or `Document project/file management and settings-based project creation`. Pull requests should include a summary, environment/schema changes, verification steps, and screenshots for UI, CSS, translation, or custom-element changes. Link related issues or task notes when available.

## Security & Configuration Tips

Never commit real `.env` secrets, credentials, logs, PID files, SQLite databases, uploaded files, or virtual environments. Keep `persist_user_env = false` unless security requirements are reviewed.
