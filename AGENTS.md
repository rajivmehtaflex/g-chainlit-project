# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Chainlit assistant with password auth, SQLite thread history, and custom UI. The entrypoint is `main.py`; it initializes `chainlit.db` from `schema.sql`, wires `SQLAlchemyDataLayer`, and defines callbacks. Chainlit config and translations live in `.chainlit/`, with welcome copy in `chainlit.md`. Static assets are under `public/`: use `public/custom.css` for global overrides and `public/elements/*.jsx` for custom elements. Reference notes live under `ref_ai/`. Runtime files such as `chainlit.db`, `chainlit.log`, `chainlit.pid`, `.files/`, `.venv/`, and `__pycache__/` are generated locally.

## Build, Test, and Development Commands

- `uv sync`: install Python 3.12 dependencies from `pyproject.toml` and `uv.lock`.
- `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`: run the app directly and initialize the local SQLite database.
- `./start.sh`: start Chainlit in the background using `CHAINLIT_PORT` from `.env`; writes `chainlit.log` and `chainlit.pid`.
- `./stop.sh`: stop the background Chainlit process started by `start.sh`.

Create a local `.env` before running the app. Required variables are `CHAINLIT_AUTH_USERNAME`, `CHAINLIT_AUTH_PASSWORD`, `STATIC_RESPONSE`, and `CHAINLIT_PORT`.

## Coding Style & Naming Conventions

Use Python 3.12 and keep style close to `main.py`: 4-space indentation, typed callback signatures, and small functions organized around Chainlit decorators. Use `snake_case` for Python names and uppercase underscore names for environment variables. Keep `schema.sql` explicit and idempotent. For custom elements, use PascalCase component filenames and exports, and rely on Chainlit globals such as `props` and `sendUserMessage`.

## Testing Guidelines

No automated test suite is currently configured. For logic or database changes, add focused `pytest` tests under a new `tests/` directory, with files named `test_*.py`. Run them with `uv run pytest` after adding `pytest` as a development dependency. Until tests exist, manually verify sign-in, new chat, resumed thread history, the `WelcomeCard` button, and the static response flow.

## Commit & Pull Request Guidelines

Current history uses concise imperative commit messages, for example `Initial Chainlit deployment with thread history and custom UI`. Continue that style with messages like `Add persisted feedback table`. Pull requests should include a summary, environment or schema changes, manual test steps, and screenshots for UI, CSS, translation, or custom element changes. Link related issues or task notes when available.

## Security & Configuration Tips

Never commit real `.env` secrets, credentials, logs, PID files, SQLite runtime databases, uploaded files, or virtual environments. Access environment variables with explicit names so missing configuration fails loudly during development. Keep `persist_user_env = false` unless there is a deliberate security review.
