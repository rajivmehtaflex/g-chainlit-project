# Repository Guidelines

## Project Structure & Module Organization

This is a Chainlit assistant with SQLite history and project-aware chat profiles. `main.py` initializes `chainlit.db` from `schema.sql` and wires auth, chat, settings, resume, and project/file callbacks. `projects.py` owns project/file persistence; `data_layer.py` stores project tags and prefixes threads with `[Project] `. `app_logging.py` configures Loguru tracing in `app_events.log`. Config is in `.chainlit/`; custom UI is in `public/`, notably `ProjectDashboard.jsx` and `ReloadPrompt.jsx`. Tests are in `tests/`; `ref_ai/` contains reference notes.

Projects are created from the Settings panel. The dashboard supports description edits, file upload/rename/delete, and confirmed project deletion. Project names are immutable because profile identity and thread tags are name-keyed. Create/delete actions require a page reload and show `ReloadPrompt`. `on_chat_resume` resolves the project from thread tags and re-sends the dashboard and settings. `_refresh_dashboard` updates the existing dashboard or sends a fallback.

Generated paths include `chainlit.db`, `project_files/`, `.files/`, logs, PID files, `.venv/`, and `__pycache__/`.

## Build, Test, and Development Commands

- `uv sync`: install Python 3.12 dependencies.
- `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`: run directly.
- `./start.sh` / `./stop.sh`: start or stop the background server using `CHAINLIT_PORT`.
- `uv run pytest`: run the test suite.
- `tail -f app_events.log` or `tail -f chainlit.log`: inspect application or Chainlit logs.

Use `.env` for `CHAINLIT_AUTH_USERNAME`, `CHAINLIT_AUTH_PASSWORD`, `CHAINLIT_AUTH_SECRET`, `STATIC_RESPONSE`, and `CHAINLIT_PORT`.

## Coding Style & Naming Conventions

Use Python 3.12, four-space indentation, typed callbacks, concise async handlers, and `snake_case` Python names. Use uppercase underscore environment variables, explicit idempotent SQL, and PascalCase JSX filenames/exports. Custom elements use Chainlit globals such as `props` and `sendUserMessage`.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio`; name files `test_*.py`. Add focused repository or logging tests for persistence and observability changes. Manually verify sign-in, new/resumed chats, project switching and `[Project]` names, Settings-panel creation/reload, dashboard edits, file operations, and confirmed deletion with tagged-thread cleanup. Upload checks must cover `Saving…/Attached…` progress, event-loop responsiveness via `asyncio.to_thread`, timeout/cancel feedback, and `app_events.log` entries.

## Commit & Pull Request Guidelines

Use concise imperative messages such as `Restore project dashboard on chat resume` or `Add loguru event tracing for upload flow`. PRs should include a summary, environment/schema changes, verification steps, and screenshots for UI, CSS, translation, or JSX changes. Link related issues or task notes when available.

## Security & Configuration Tips

Never commit `.env` secrets, credentials, logs, PID files, SQLite databases, uploaded files, or virtual environments. Keep `persist_user_env = false` unless security requirements are reviewed.
