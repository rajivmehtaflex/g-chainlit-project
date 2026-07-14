# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Chainlit assistant with SQLite thread history. The entrypoint is `main.py`; it initializes `chainlit.db` from `schema.sql` and wires callbacks for auth, chat profiles, chat start/resume, messages, settings updates, and project/file action callbacks. Persistence is split into `projects.py` for the SQLite project/file store (create, edit description, delete, plus file add/rename/delete) and `data_layer.py` for `ProjectDataLayer`, which prefixes project thread names with `[Project] `. New projects are created through Chainlit's Settings panel (gear icon); project renaming is unsupported by design (thread tags are name-keyed), and create/delete require a manual page reload to update the dropdown/sidebar (surfaced via `ReloadPrompt.jsx`). Chainlit config and translations live in `.chainlit/`, with welcome copy in `chainlit.md`. Static assets are under `public/`, including `public/custom.css` and `public/elements/*.jsx` (`ProjectDashboard.jsx`, `ReloadPrompt.jsx`). Runtime files such as `chainlit.db`, `chainlit.log`, `chainlit.pid`, `.files/`, `project_files/`, `.venv/`, and `__pycache__/` are generated locally.

## Build, Test, and Development Commands

- `uv sync`: install Python 3.12 dependencies from `pyproject.toml` and `uv.lock`.
- `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`: run the app directly and initialize the local SQLite database.
- `./start.sh`: start Chainlit in the background using `CHAINLIT_PORT` from `.env`; writes `chainlit.log` and `chainlit.pid`.
- `./stop.sh`: stop the background Chainlit process started by `start.sh`.

Create a local `.env` before running the app. Required variables are `CHAINLIT_AUTH_USERNAME`, `CHAINLIT_AUTH_PASSWORD`, `STATIC_RESPONSE`, and `CHAINLIT_PORT`.

## Coding Style & Naming Conventions

Use Python 3.12 and keep style close to `main.py`: 4-space indentation, typed callback signatures, and small functions organized around Chainlit decorators. Use `snake_case` for Python names and uppercase underscore names for environment variables. Keep `schema.sql` explicit and idempotent. For custom elements, use PascalCase filenames and exports, and rely on Chainlit globals such as `props` and `sendUserMessage`.

## Testing Guidelines

`pytest` is configured; tests live under `tests/` as `test_*.py` (27 tests). Run the suite with `uv run pytest`, or a focused test such as `uv run pytest tests/test_projects.py::test_create_and_get_project -v`. Add focused tests alongside the existing ones. Action callbacks and the settings panel have no automated coverage — manually verify sign-in, new chat, resumed thread history, project switching, `[Project]` prefixes, file attach flow, project creation via the Settings panel (then reload), description edit, file rename (including duplicate-name rejection) and delete, and project deletion cascading to tagged threads (then reload).

## Commit & Pull Request Guidelines

Current history uses concise imperative commit messages, for example `Add ProjectDashboard custom element` or `Sanitize uploaded file names in add_project_file`. Continue that style. Pull requests should include a summary, environment or schema changes, manual test steps, and screenshots for UI, CSS, translation, or custom element changes. Link related issues or task notes when available.

## Security & Configuration Tips

Never commit real `.env` secrets, credentials, logs, PID files, SQLite runtime databases, uploaded files, or virtual environments. Access environment variables with explicit names so missing configuration fails loudly during development. Keep `persist_user_env = false` unless there is a deliberate security review.
