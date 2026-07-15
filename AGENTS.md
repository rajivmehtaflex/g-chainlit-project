# Repository Guidelines

## Project Structure & Module Organization

This Chainlit assistant uses Python 3.12, `uv`, and SQLite history. `main.py` initializes `chainlit.db` from idempotent `schema.sql` and wires callbacks. `projects.py` persists projects/files; `data_layer.py` serializes SQLite tags, adds `[Project] ` names, and searches thread names plus step output. Config is in `.chainlit/`; UI is in `public/`; tests are in `tests/`.

Projects are created from the gear Settings panel. The dashboard edits descriptions, manages files, and supports typed-confirmation deletion. Names are immutable because profiles and tags are name-keyed. Chainlit does not persist the dashboard: `on_chat_resume` resolves tags, then uses an `asyncio.create_task` retained in `user_session` to send dashboard/settings after 0.5 seconds, avoiding the stale snapshot. Diagnose with `chat_resume deferred UI sent` or `failed` in `app_events.log`.

## Build, Test, and Development Commands

- `uv sync`: install dependencies.
- `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`: run.
- `./start.sh` / `./stop.sh`: manage the background server using `CHAINLIT_PORT`.
- `uv run pytest`: run 28 tests.
- `tail -f chainlit.log`: inspect Chainlit output; `tail -f app_events.log` or `grep INFO app_events.log`: inspect events.

Use `.env` for auth credentials/secret, `STATIC_RESPONSE`, and `CHAINLIT_PORT`.

## Coding Style & Naming Conventions

Use four-space indentation, typed callbacks, concise async handlers, `snake_case` Python names, uppercase underscore environment variables, explicit idempotent SQL, and PascalCase JSX filenames/exports. Custom elements use `props` and `sendUserMessage`.

## Runtime and Upload Notes

`app_logging.py` writes a Loguru sink to `app_events.log` with 10 MB rotation and 7-day retention. INFO records actions; DEBUG records background events. Login, projects, actions, uploads, and data-layer calls are traced. Uploads use `cl.AskFileMessage` with 200 MB/300-second limits; Stop Task is expected during the dropzone. Copies use `asyncio.to_thread`, show progress, report timeout/cancel, store files under `project_files/<id>/`, and filter the blob warning.

## Testing Guidelines

Tests use `pytest` and `pytest-asyncio`; name files `test_*.py`. Add focused repository/logging tests. Verify auth, new/resumed chats, sidebar loading, project switching, Settings reload, dashboard/file operations, upload feedback, and tagged-thread cleanup. On resume, confirm the dashboard appears about 0.5 seconds after history and success logging is present.

## Commit & Pull Request Guidelines

Use concise imperative messages such as `Trace every UI-triggered hook` or `Fix deferred dashboard resume UI`. PRs should include summary, schema changes, verification steps, and screenshots for UI/CSS/JSX changes. Link related issues or task notes.

## Security & Configuration Tips

Never commit `.env` secrets, credentials, databases, uploads, logs, PID files, or virtual environments. Keep `persist_user_env = false` unless security requirements are reviewed.
