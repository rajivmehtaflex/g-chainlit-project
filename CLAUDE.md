# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**G-Chainlit Assistant** is a password-authenticated Chainlit application with SQLite-based thread history, custom styling, and JSX components. The backend is Python 3.12 (using `uv` for package management), the frontend is the built-in Chainlit UI with CSS and React component customizations. Entrypoint: `main.py`. Database schema lives in `schema.sql`; config in `.chainlit/config.toml`.

## Architecture & Key Concepts

### Backend (Python)
- **`main.py`**: Wiring only — initializes SQLite database from `schema.sql`, registers Chainlit callbacks (`@cl.password_auth_callback`, `@cl.data_layer`, `@cl.set_chat_profiles`, `@cl.on_chat_start`, `@cl.on_message`, `@cl.on_chat_resume`, `@cl.on_settings_update`) and action callbacks (`add_project_files`, `update_project_description`, `delete_project`, `rename_project_file`, `delete_project_file`). `set_chat_profiles` offers the `General` default plus one profile per row in the `projects` table (seeded with Dryback/Crystal); `on_chat_start` sends the `ProjectDashboard` custom element and a `cl.ChatSettings` panel; `on_chat_resume` restores the active project from thread tags and re-sends both the `ProjectDashboard` and the settings panel — the dashboard is *not* persisted or replayed by Chainlit (no `storage_provider` is configured, so `create_element` is a no-op) and must be explicitly re-sent on every resume, the same way `on_chat_start` sends it; `on_settings_update` creates a new project from the settings-panel fields; `on_message` still returns the static response. Project *creation* happens via the gear-icon Settings panel, not an action callback. Project *renaming* is unsupported by design — thread `tags` and chat-profile identity are name-keyed (`data_layer.py`/`on_chat_resume` resolve projects by name), so only the description is editable. Any change to the projects table (create or delete) requires a manual page reload to appear in the profile dropdown or thread sidebar — Chainlit has no backend push to refresh those — so those flows send a `ReloadPrompt` element. The `from chainlit.data import get_data_layer as get_active_data_layer` import is aliased to avoid shadowing the module's own `get_data_layer()` data-layer factory.
- **`projects.py`**: Project/file repository backed by SQLite (`projects`, `project_files` tables) using synchronous `sqlite3`. Exposes `create_project`, `get_project`, `list_projects`, `update_project_description`, `delete_project` (cascades files + directory), `add_project_file` (copies uploads into `project_files/<project_id>/`), `list_project_files`, `get_project_file`, `rename_project_file`, `delete_project_file`, `ensure_seed_projects`, and the `GENERAL_PROFILE` constant ("General").
- **`data_layer.py`**: `ProjectDataLayer(SQLAlchemyDataLayer)` — JSON-serializes thread `tags` before binding them for SQLite (the stock layer binds a Python list, which sqlite3 rejects, and `execute_sql` silently swallows the error); prefixes thread names with `[Project] ` when tagged with a non-General project; extends sidebar search to match thread names in addition to step output.
- **`schema.sql`**: SQLite schema used by Chainlit's `SQLAlchemyDataLayer` to store users, threads, steps, elements, and feedbacks, plus the `projects` and `project_files` tables for project mode. Idempotent CREATE TABLE statements.
- **Database**: `chainlit.db` (SQLite, auto-initialized on startup from `schema.sql`).
- **`app_logging.py`**: Configures a dedicated `loguru` sink writing to `app_events.log` (rotated at 10 MB, retained 7 days) — separate from Chainlit's own `chainlit.log`. `main.py` and `data_layer.py` import its `logger` to trace every UI-triggered hook: session lifecycle (`chat_start`/`chat_resume`), login, project create/delete (including cascade counts), dashboard refresh (`dashboard sent`/`dashboard refreshed in place`/fallback), the upload flow (batch + per-file timing, timeout/cancel), all 5 action callbacks (unconditional entry log, so a dropped click is distinguishable from a stalled one), and the sidebar/thread data-layer methods. Entries are tagged `INFO` for discrete deliberate actions or `DEBUG` for high-frequency background events (`chat_profiles`, `on_message`, thread listing/search/tagging) — use `grep INFO app_events.log` to see only the meaningful actions, or `tail -f app_events.log` for everything.

### Frontend & Customization
- **Config**: `.chainlit/config.toml` controls project settings (theme, sidebar state, custom CSS, features like file upload).
- **Custom CSS**: `public/custom.css` overrides Chainlit's default styling; sets primary color to purple, message radius, hides the default Chainlit link and replaces it with "G-Chainlit Assistant".
- **Custom JSX Components**: `public/elements/ProjectDashboard.jsx` is sent via `cl.CustomElement` in `on_chat_start`, showing the active project's name, editable description, per-file rename/delete controls, an upload button, and a typed-confirmation "delete project" danger zone (or a project-less state). `public/elements/ReloadPrompt.jsx` is sent after project create/delete with a "Reload now" button (`window.location.reload()`). `public/elements/WelcomeCard.jsx` still exists but is no longer sent.
- **File uploads**: the dashboard's "Add files" button triggers `on_add_project_files`, which uses `cl.AskFileMessage` (cap `UPLOAD_MAX_MB`=200, `timeout` `UPLOAD_TIMEOUT_S`=300s). While the upload dropzone is open the "Stop Task" indicator is lit for the whole callback — this is inherent to Chainlit's action-callback task model, not a hang. Files are copied off the event loop via `asyncio.to_thread(projects.add_project_file, …)` so large/many-file uploads don't freeze the app; a "Saving…"/"Attached…" message gives progress, and a timed-out/cancelled upload gets an explicit message instead of silence. Project files live in `project_files/<id>/` + the `project_files` table (the authoritative store the dashboard reads); Chainlit's own blob-element persistence is intentionally unused, and its `No blob_storage_client is configured` warning is filtered in `main.py`.

### Authentication & Data Persistence
- **Password Auth**: `@cl.password_auth_callback` in `main.py` validates credentials against `CHAINLIT_AUTH_USERNAME` and `CHAINLIT_AUTH_PASSWORD` from `.env`. Returns `cl.User` on success, `None` on failure.
- **Data Layer**: `SQLAlchemyDataLayer` with SQLite connection string enables the thread history sidebar (appears only when logged in and `dataPersistence` is true in config).

### Deployment
- **Development**: `uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless`
- **Background**: `./start.sh` launches Chainlit via `setsid nohup`, stores PID in `chainlit.pid`, logs to `chainlit.log`. `./stop.sh` kills the process group.

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run the app directly (port from CLI argument or .env CHAINLIT_PORT)
uv run chainlit run main.py --host 0.0.0.0 --port 8000 --headless

# Start in background
./start.sh

# Stop background process
./stop.sh

# View logs (if running via start.sh)
tail -f chainlit.log

# Run the test suite
uv run pytest
```

## Environment Variables

Required (must be set in `.env` before running):
- `CHAINLIT_AUTH_USERNAME`: Login username
- `CHAINLIT_AUTH_PASSWORD`: Login password
- `CHAINLIT_AUTH_SECRET`: JWT secret for session signing (generate with `chainlit create-secret`)
- `CHAINLIT_PORT`: Port number (e.g., 8890)
- `STATIC_RESPONSE`: Hardcoded message returned by `on_message`

Never commit real `.env` files; they contain secrets.

## Code Structure & File Locations

| Path | Purpose |
|------|---------|
| `main.py` | Entry point; database init, Chainlit callbacks |
| `projects.py` | Project/file repository (SQLite); `GENERAL_PROFILE` constant |
| `data_layer.py` | `ProjectDataLayer`: SQLite-safe tags, `[Project] ` naming, thread search |
| `schema.sql` | SQLite schema for users, threads, steps, elements, feedbacks, projects, project_files |
| `.chainlit/config.toml` | Project config (UI name, theme, custom CSS, features) |
| `.chainlit/translations/` | Language files (auto-generated by Chainlit init) |
| `public/custom.css` | Global CSS overrides |
| `public/elements/WelcomeCard.jsx` | Custom React component (greeting card, no longer sent) |
| `public/elements/ProjectDashboard.jsx` | Custom React component; project name, editable description, file rename/delete, delete-project |
| `public/elements/ReloadPrompt.jsx` | Custom React component; "Reload now" button, sent after project create/delete |
| `pyproject.toml` | Python dependencies and project metadata |
| `start.sh` / `stop.sh` | Background process management scripts |

Generated/runtime files (gitignored):
- `chainlit.db` — SQLite database
- `chainlit.log` — Log output from background process
- `chainlit.pid` — Process ID of background Chainlit
- `.files/` — Uploaded user files
- `project_files/` — Project files copied on attach, under `project_files/<project_id>/`
- `__pycache__/` — Python bytecode

## Coding Style & Conventions

### Python
- Use Python 3.12.
- Follow style in `main.py`: 4-space indentation, typed function signatures.
- Use `snake_case` for functions and variables.
- Use `UPPERCASE_UNDERSCORE` for environment variable names.
- Keep Chainlit decorator callbacks concise; delegate complex logic to helper functions.
- Load `.env` with `from dotenv import load_dotenv; load_dotenv()`.

### SQL
- Keep `schema.sql` explicit and idempotent (all `CREATE TABLE IF NOT EXISTS`).
- Use column names that match the `SQLAlchemyDataLayer` API (see comments in `schema.sql`).

### JSX/CSS
- Custom components in `public/elements/` use PascalCase filenames and exports (e.g., `WelcomeCard.jsx`).
- Rely on Chainlit globals: `props` (component props from Python), `sendUserMessage()` (send user messages).
- CSS uses CSS variables (e.g., `--primary`, `--chat-radius`) defined in `custom.css`; Tailwind classes work in component className.

## Testing

`uv run pytest` runs the suite in `tests/` (27 tests: 22 in `test_projects.py`, 5 in `test_data_layer.py`). To run a single test: `uv run pytest tests/test_projects.py::test_create_and_get_project -v`.

In addition to the automated suite, manually verify (action callbacks and the settings panel have no automated coverage — they need a live browser):
- User sign-in with correct/incorrect credentials
- New chat creation and thread resumption
- Thread history sidebar appears/loads correctly
- ProjectDashboard renders correctly for General and for an active project
- Static response flow (user message → hardcoded response)
- Project switching via the chat profile dropdown
- `[Project]` thread name prefixes appear in the sidebar
- Project file attach flow (upload via dashboard action, files listed afterward)
- New project created via the Settings panel (gear icon), then reload to see it in the dropdown
- Description edit updates the card in place
- File rename (including duplicate-name rejection) and file delete
- Project deletion cascades to its tagged threads, then reload to update dropdown and sidebar

## Pull Requests & Commits

- **Commit messages**: Use concise imperative style (e.g., "Add feedback table", "Fix auth callback race condition").
- **PR description**: Include summary, environment/schema changes, manual test steps, and screenshots for UI/CSS/component changes.
- **Link context**: Reference related issues or task notes in the PR body.

## Security Notes

- **Never commit** `.env` files with real secrets, credentials, database files, logs, or PID files.
- **Keep `persist_user_env = false`** in `config.toml` (security default; only set to true after security review).
- **Environment variables** are accessed by explicit name in code (e.g., `os.environ["CHAINLIT_AUTH_PASSWORD"]`), so missing config fails loudly during development.
- **Password auth** uses JWT with a secret from `CHAINLIT_AUTH_SECRET`; regenerate the secret if sessions must be invalidated.

## Key Dependencies

- **chainlit** (≥2.11.1): Chatbot framework.
- **sqlalchemy** (≥2.0.51): ORM for data layer.
- **aiosqlite** (≥0.22.1): Async SQLite driver.
- **python-dotenv** (≥1.2.2): Load `.env` files.
- **uv**: Fast Python package manager and runner.
- **pytest** (≥9.1.1) / **pytest-asyncio** (≥1.4.0): dev-only, test suite in `tests/`.

## Tips for Development

1. **Modify the project dashboard**: Edit `public/elements/ProjectDashboard.jsx` or the props built by `_dashboard_props()` in `main.py`.
2. **Change styling**: Update `public/custom.css` or variables in `.chainlit/config.toml`.
3. **Add new callbacks**: Use `@cl.on_message`, `@cl.on_chat_start`, `@cl.on_chat_resume` in `main.py`. Callbacks run in async context.
4. **Extend the schema**: Add tables to `schema.sql`; next startup will run idempotent CREATE statements.
5. **Connect to an LLM**: Replace the static `STATIC_RESPONSE` in `on_message` with LLM API calls (e.g., Claude API, OpenAI).
6. **Enable chat settings**: Uncomment `# [UI.chat_settings_location = "sidebar"]` in `config.toml` to let users configure the assistant.
