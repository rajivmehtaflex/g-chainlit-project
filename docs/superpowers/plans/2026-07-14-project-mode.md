# Project Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Project" mode to the Chainlit assistant: threads and shared files grouped per project (client), selectable via the chat-profile dropdown, with an in-chat dashboard for creating projects and attaching files.

**Architecture:** Chat profiles act as the project selector (one profile per row in a new `projects` SQLite table, plus a default "General" profile that preserves today's session-mode behavior). A `ProjectDataLayer` subclass of `SQLAlchemyDataLayer` fixes SQLite tag persistence (JSON-serialized), prefixes thread names with `[Project] `, and extends sidebar search to match thread names. A `ProjectDashboard` custom element (rendered in the first message) provides project CRUD via `callAction`; project files are copied into `project_files/<project_id>/` and recorded in a `project_files` table.

**Tech Stack:** Python 3.12, Chainlit 2.11.1, SQLite (sqlite3 + aiosqlite), pytest + pytest-asyncio, JSX custom elements (shadcn UI, lucide-react).

## Global Constraints

- Python 3.12; run everything through `uv` (`uv run ...`, `uv add ...`).
- The app must keep working exactly as today when the "General" profile is active (static response, WelcomeCard-style greeting, per-session uploads).
- `schema.sql` stays idempotent (`CREATE TABLE IF NOT EXISTS` only); it is executed on every startup by `_init_db()` in `main.py`.
- Custom elements: JSX only (no TypeScript), file at `public/elements/<Name>.jsx`, must use globals `props`, `callAction`, `updateElement` (never destructure props as a function parameter), imports limited to React, shadcn `@/components/ui/*`, lucide-react, zod, react-hook-form, sonner, recoil.
- SQLite cannot bind Python lists: any `tags` value passed to SQL must be JSON-serialized first (verified: `sqlite3.ProgrammingError: type 'list' is not supported`, and Chainlit's `execute_sql` swallows the error, silently dropping the whole INSERT).
- Environment variables accessed by explicit name (`os.environ["X"]`), commit messages in concise imperative style.
- Chat profile names ARE project names (the emitter tags threads with `session.chat_profile` verbatim — see `.venv/.../chainlit/emitter.py:245`).

## File Structure

- `schema.sql` (modify) — add `projects` and `project_files` tables.
- `projects.py` (create) — synchronous SQLite repository: project CRUD, file attachment, seeding. Owns `GENERAL_PROFILE` constant and `PROJECT_FILES_DIR`.
- `data_layer.py` (create) — `ProjectDataLayer` (moved out of `main.py` PoC code): SQLite-safe tags, `[Project] ` name prefix, name-aware sidebar search.
- `main.py` (modify) — wiring only: auth, dynamic chat profiles, `on_chat_start` dashboard, action callbacks, static `on_message`.
- `public/elements/ProjectDashboard.jsx` (create) — project card: description, file list, "Add files" button, "New project" form.
- `tests/test_projects.py`, `tests/test_data_layer.py` (create) — pytest suites.
- `pyproject.toml` (modify) — dev deps + pytest config.
- `.gitignore` (modify) — add `project_files/`.

---

### Task 1: Test infrastructure + projects repository

**Files:**
- Modify: `pyproject.toml`
- Modify: `schema.sql`
- Create: `projects.py`
- Test: `tests/test_projects.py`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces (used by Tasks 2, 3, 5):
  - `projects.GENERAL_PROFILE: str = "General"`
  - `projects.PROJECT_FILES_DIR: Path`
  - `projects.create_project(name: str, description: str = "", db_path: Path | None = None) -> dict` — raises `ValueError` on blank/duplicate name; returns `{"id", "name", "description", "createdAt"}`.
  - `projects.get_project(name: str, db_path: Path | None = None) -> dict | None`
  - `projects.list_projects(db_path: Path | None = None) -> list[dict]` — ordered by name.
  - `projects.add_project_file(project_id: str, name: str, source_path: str, mime: str, size: int, db_path: Path | None = None, files_dir: Path | None = None) -> dict` — copies the source file to `<files_dir>/<project_id>/<name>` and inserts a row; returns `{"id", "projectId", "name", "path", "mime", "size", "createdAt"}`.
  - `projects.list_project_files(project_id: str, db_path: Path | None = None) -> list[dict]` — ordered by createdAt.
  - `projects.ensure_seed_projects(names: list[str], db_path: Path | None = None) -> None` — idempotent.

- [ ] **Step 1: Add dev dependencies and pytest config**

Run: `uv add --dev pytest pytest-asyncio`

Then append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Add tables to `schema.sql`**

Append to `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    createdAt TEXT
);

CREATE TABLE IF NOT EXISTS project_files (
    id TEXT PRIMARY KEY,
    projectId TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    mime TEXT,
    size INTEGER,
    createdAt TEXT
);
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_projects.py`:

```python
import sqlite3
from pathlib import Path

import pytest

import projects

APP_DIR = Path(__file__).parent.parent
SCHEMA_PATH = APP_DIR / "schema.sql"


@pytest.fixture
def db_path(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def files_dir(tmp_path):
    return tmp_path / "project_files"


def test_create_and_get_project(db_path):
    created = projects.create_project("Dryback", "E-commerce, London", db_path=db_path)
    assert created["name"] == "Dryback"
    assert created["description"] == "E-commerce, London"
    assert created["id"]

    fetched = projects.get_project("Dryback", db_path=db_path)
    assert fetched == created


def test_get_missing_project_returns_none(db_path):
    assert projects.get_project("Nope", db_path=db_path) is None


def test_create_duplicate_raises(db_path):
    projects.create_project("Dryback", db_path=db_path)
    with pytest.raises(ValueError, match="already exists"):
        projects.create_project("Dryback", db_path=db_path)


def test_create_blank_name_raises(db_path):
    with pytest.raises(ValueError, match="required"):
        projects.create_project("   ", db_path=db_path)


def test_list_projects_ordered_by_name(db_path):
    projects.create_project("Crystal", db_path=db_path)
    projects.create_project("Dryback", db_path=db_path)
    names = [p["name"] for p in projects.list_projects(db_path=db_path)]
    assert names == ["Crystal", "Dryback"]


def test_add_and_list_project_files(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"%PDF-fake")

    rec = projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 9,
        db_path=db_path, files_dir=files_dir,
    )
    stored = Path(rec["path"])
    assert stored.exists()
    assert stored.parent == files_dir / project["id"]
    assert stored.read_bytes() == b"%PDF-fake"

    listed = projects.list_project_files(project["id"], db_path=db_path)
    assert [f["name"] for f in listed] == ["report.pdf"]


def test_ensure_seed_projects_idempotent(db_path):
    projects.ensure_seed_projects(["Dryback", "Crystal"], db_path=db_path)
    projects.ensure_seed_projects(["Dryback", "Crystal"], db_path=db_path)
    assert len(projects.list_projects(db_path=db_path)) == 2
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_projects.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'projects'`

- [ ] **Step 5: Implement `projects.py`**

Create `projects.py`:

```python
"""Project repository: projects and their shared files, stored in chainlit.db.

Synchronous sqlite3 is deliberate: operations are tiny and this keeps the
module usable from both Chainlit's async callbacks and plain scripts/tests.
"""

import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "chainlit.db"
PROJECT_FILES_DIR = APP_DIR / "project_files"

GENERAL_PROFILE = "General"


def _connect(db_path: Optional[Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project(name: str, description: str = "", db_path: Optional[Path] = None) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Project name is required")
    if name == GENERAL_PROFILE:
        raise ValueError(f"'{GENERAL_PROFILE}' is reserved")
    project = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description.strip(),
        "createdAt": _now(),
    }
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO projects (id, name, description, createdAt) VALUES (?, ?, ?, ?)",
            (project["id"], project["name"], project["description"], project["createdAt"]),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Project '{name}' already exists")
    finally:
        conn.close()
    return project


def get_project(name: str, db_path: Optional[Path] = None) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def list_projects(db_path: Optional[Path] = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def add_project_file(
    project_id: str,
    name: str,
    source_path: str,
    mime: str,
    size: int,
    db_path: Optional[Path] = None,
    files_dir: Optional[Path] = None,
) -> dict:
    dest_dir = (files_dir or PROJECT_FILES_DIR) / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    shutil.copy2(source_path, dest)

    record = {
        "id": str(uuid.uuid4()),
        "projectId": project_id,
        "name": name,
        "path": str(dest),
        "mime": mime,
        "size": size,
        "createdAt": _now(),
    }
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO project_files (id, projectId, name, path, mime, size, createdAt)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"], record["projectId"], record["name"], record["path"],
                record["mime"], record["size"], record["createdAt"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def list_project_files(project_id: str, db_path: Optional[Path] = None) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM project_files WHERE projectId = ? ORDER BY createdAt",
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def ensure_seed_projects(names: list[str], db_path: Optional[Path] = None) -> None:
    for name in names:
        if get_project(name, db_path=db_path) is None:
            create_project(name, db_path=db_path)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_projects.py -v`
Expected: all 7 tests PASS

- [ ] **Step 7: Add `project_files/` to `.gitignore`**

Append to the `# Chainlit runtime artifacts` section of `.gitignore`:

```
project_files/
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock schema.sql projects.py tests/test_projects.py .gitignore
git commit -m "Add projects repository with shared project files"
```

---

### Task 2: ProjectDataLayer in its own module

**Files:**
- Create: `data_layer.py`
- Modify: `main.py` (remove the PoC `ProjectDataLayer` class and its `json` import; import from `data_layer` instead)
- Test: `tests/test_data_layer.py`

**Interfaces:**
- Consumes: `projects.GENERAL_PROFILE` (Task 1).
- Produces (used by Task 3): `data_layer.ProjectDataLayer(conninfo: str)` — drop-in replacement for `SQLAlchemyDataLayer` with:
  - `update_thread(...)` — JSON-serializes `tags` for SQLite; prefixes `name` with `[<first tag>] ` unless the tag is `GENERAL_PROFILE` or the prefix is already present.
  - `get_all_user_threads(...)` — parses JSON-string tags back to lists.
  - `list_threads(pagination, filters)` — like upstream, but the search keyword also matches thread **names** (upstream only scans step outputs; see `.venv/.../chainlit/data/sql_alchemy.py:343`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_data_layer.py`:

```python
import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from chainlit.types import Pagination, ThreadFilter

from data_layer import ProjectDataLayer

APP_DIR = Path(__file__).parent.parent
SCHEMA_PATH = APP_DIR / "schema.sql"


@pytest.fixture
def layer(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()
    dl = ProjectDataLayer(conninfo=f"sqlite+aiosqlite:///{db}")
    dl._test_db = db
    return dl


def _row(layer, thread_id, cols="name, tags"):
    return sqlite3.connect(layer._test_db).execute(
        f"SELECT {cols} FROM threads WHERE id=?", (thread_id,)
    ).fetchone()


async def test_tags_written_as_json_and_name_prefixed(layer):
    tid = str(uuid.uuid4())
    await layer.update_thread(thread_id=tid, name="Cash flow Q3", tags=["Dryback"])
    name, tags = _row(layer, tid)
    assert name == "[Dryback] Cash flow Q3"
    assert json.loads(tags) == ["Dryback"]


async def test_prefix_not_duplicated_on_second_update(layer):
    tid = str(uuid.uuid4())
    await layer.update_thread(thread_id=tid, name="Cash flow Q3", tags=["Dryback"])
    await layer.update_thread(thread_id=tid, name="Cash flow Q3", tags=["Dryback"])
    name, _ = _row(layer, tid)
    assert name == "[Dryback] Cash flow Q3"


async def test_general_profile_gets_no_prefix(layer):
    tid = str(uuid.uuid4())
    await layer.update_thread(thread_id=tid, name="Quick question", tags=["General"])
    name, tags = _row(layer, tid)
    assert name == "Quick question"
    assert json.loads(tags) == ["General"]


async def test_get_all_user_threads_parses_tags(layer):
    tid = str(uuid.uuid4())
    await layer.update_thread(thread_id=tid, name="Cash flow Q3", tags=["Dryback"])
    threads = await layer.get_all_user_threads(thread_id=tid)
    assert threads[0]["tags"] == ["Dryback"]


async def _make_user(layer):
    import chainlit as cl
    return await layer.create_user(cl.User(identifier="admin"))


async def test_list_threads_search_matches_thread_name(layer):
    user = await _make_user(layer)
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    await layer.update_thread(thread_id=t1, name="Cash flow", user_id=user.id, tags=["Dryback"])
    await layer.update_thread(thread_id=t2, name="Report", user_id=user.id, tags=["Crystal"])

    res = await layer.list_threads(
        Pagination(first=20), ThreadFilter(userId=user.id, search="dryback")
    )
    names = [t["name"] for t in res.data]
    assert names == ["[Dryback] Cash flow"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_data_layer.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'data_layer'`

- [ ] **Step 3: Implement `data_layer.py`**

Create `data_layer.py`:

```python
"""SQLAlchemyDataLayer adapted for SQLite and project-tagged threads."""

import json
from typing import Optional

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import PageInfo, PaginatedResponse, Pagination, ThreadFilter

from projects import GENERAL_PROFILE


class ProjectDataLayer(SQLAlchemyDataLayer):
    """Fixes SQLite tag persistence and adds project-aware thread naming/search.

    The stock layer binds `tags` as a Python list, which sqlite3 rejects —
    and execute_sql swallows the error, silently dropping the whole thread
    INSERT. Tags are therefore stored as a JSON string and parsed on read.
    """

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        tags: Optional[list] = None,
    ):
        if name and tags and tags[0] != GENERAL_PROFILE:
            prefix = f"[{tags[0]}] "
            if not name.startswith(prefix):
                name = prefix + name
        if tags is not None:
            tags = json.dumps(tags)
        await super().update_thread(
            thread_id=thread_id, name=name, user_id=user_id, metadata=metadata, tags=tags
        )

    async def get_all_user_threads(self, user_id=None, thread_id=None):
        threads = await super().get_all_user_threads(user_id=user_id, thread_id=thread_id)
        for thread in threads or []:
            if isinstance(thread.get("tags"), str):
                try:
                    thread["tags"] = json.loads(thread["tags"])
                except json.JSONDecodeError:
                    thread["tags"] = []
        return threads

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse:
        # Mirrors the upstream implementation, except the search keyword also
        # matches thread names so "[Project]" prefixes are searchable
        # (upstream only scans step outputs).
        if not filters.userId:
            raise ValueError("userId is required")
        all_user_threads = await self.get_all_user_threads(user_id=filters.userId) or []

        search_keyword = filters.search.lower() if filters.search else None
        feedback_value = int(filters.feedback) if filters.feedback else None

        filtered_threads = []
        for thread in all_user_threads:
            keyword_match = True
            feedback_match = True
            if search_keyword:
                name_match = search_keyword in (thread.get("name") or "").lower()
                step_match = any(
                    search_keyword in step["output"].lower()
                    for step in thread["steps"]
                    if "output" in step
                )
                keyword_match = name_match or step_match
            if feedback_value is not None:
                feedback_match = False
                for step in thread["steps"]:
                    feedback = step.get("feedback")
                    if feedback and feedback.get("value") == feedback_value:
                        feedback_match = True
                        break
            if keyword_match and feedback_match:
                filtered_threads.append(thread)

        start = 0
        if pagination.cursor:
            for i, thread in enumerate(filtered_threads):
                if thread["id"] == pagination.cursor:
                    start = i + 1
                    break
        end = start + pagination.first
        paginated_threads = filtered_threads[start:end] or []

        has_next_page = len(filtered_threads) > end
        start_cursor = paginated_threads[0]["id"] if paginated_threads else None
        end_cursor = paginated_threads[-1]["id"] if paginated_threads else None

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=start_cursor,
                endCursor=end_cursor,
            ),
            data=paginated_threads,
        )
```

- [ ] **Step 4: Remove the PoC class from `main.py`**

In `main.py`: delete the whole `class ProjectDataLayer(SQLAlchemyDataLayer): ...` block, the now-unused `import json`, and the `from chainlit.data.sql_alchemy import SQLAlchemyDataLayer` import. Add `from data_layer import ProjectDataLayer` below the other imports. Keep everything else exactly as-is — including the `PROJECTS = ["Dryback", "Crystal"]` constant and the `@cl.set_chat_profiles` function that reads it (Task 3 replaces both), and `get_data_layer()` still returning `ProjectDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")`.

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: all tests PASS (7 from Task 1 + 5 here)

- [ ] **Step 6: Verify the app still boots**

Run: `./stop.sh; ./start.sh; sleep 6; tail -3 chainlit.log`
Expected: `Your app is available at http://0.0.0.0:8890`, no tracebacks

- [ ] **Step 7: Commit**

```bash
git add data_layer.py main.py tests/test_data_layer.py
git commit -m "Extract ProjectDataLayer with name-aware sidebar search"
```

---

### Task 3: Dynamic chat profiles + project session wiring

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `projects.list_projects`, `projects.get_project`, `projects.ensure_seed_projects`, `projects.list_project_files`, `projects.GENERAL_PROFILE` (Task 1).
- Produces (used by Tasks 4, 5):
  - `cl.user_session["project"]` — the active project dict or `None` (General mode), set in both `on_chat_start` and `on_chat_resume`.
  - `cl.user_session["dashboard_el"]` — the `ProjectDashboard` `cl.CustomElement` instance (project mode only), so action callbacks can `update()` it.
  - `_dashboard_props(project: dict) -> dict` — helper building `{"name", "description", "files": [{"name", "size"}]}`.

- [ ] **Step 1: Rewrite `main.py`**

Replace the full contents of `main.py` with:

```python
import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import chainlit as cl
from chainlit.types import ThreadDict

import projects
from data_layer import ProjectDataLayer
from projects import GENERAL_PROFILE

load_dotenv()

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "chainlit.db"
SCHEMA_PATH = APP_DIR / "schema.sql"

SEED_PROJECTS = ["Dryback", "Crystal"]


def _init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()


_init_db()
projects.ensure_seed_projects(SEED_PROJECTS)


@cl.data_layer
def get_data_layer():
    return ProjectDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if (
        username == os.environ["CHAINLIT_AUTH_USERNAME"]
        and password == os.environ["CHAINLIT_AUTH_PASSWORD"]
    ):
        return cl.User(identifier=username, metadata={"role": "ADMIN"})
    return None


@cl.set_chat_profiles
async def chat_profiles(current_user: Optional[cl.User]):
    profiles = [
        cl.ChatProfile(
            name=GENERAL_PROFILE,
            markdown_description="Ad-hoc chats that don't belong to a project.",
            default=True,
        )
    ]
    for project in projects.list_projects():
        profiles.append(
            cl.ChatProfile(
                name=project["name"],
                markdown_description=project["description"]
                or f"Workspace for **{project['name']}**.",
            )
        )
    return profiles


def _dashboard_props(project: dict) -> dict:
    files = projects.list_project_files(project["id"])
    return {
        "name": project["name"],
        "description": project["description"],
        "files": [{"name": f["name"], "size": f["size"]} for f in files],
    }


async def _send_dashboard(project: Optional[dict], greeting: str) -> None:
    props = _dashboard_props(project) if project else {"name": None, "description": "", "files": []}
    dashboard = cl.CustomElement(name="ProjectDashboard", props=props)
    cl.user_session.set("dashboard_el", dashboard)
    await cl.Message(content=greeting, elements=[dashboard]).send()


@cl.on_chat_start
async def on_chat_start():
    user = cl.user_session.get("user")
    profile = cl.user_session.get("chat_profile")
    project = (
        projects.get_project(profile)
        if profile and profile != GENERAL_PROFILE
        else None
    )
    cl.user_session.set("project", project)
    if project:
        greeting = f"Hello {user.identifier}! Project **{project['name']}** is active."
    else:
        greeting = f"Hello {user.identifier}! How can I help you today?"
    await _send_dashboard(project, greeting)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    tags = thread.get("tags") or []
    project = None
    for tag in tags:
        if tag != GENERAL_PROFILE:
            project = projects.get_project(tag)
            if project:
                break
    cl.user_session.set("project", project)


@cl.on_message
async def on_message(message: cl.Message):
    await cl.Message(content=os.environ["STATIC_RESPONSE"]).send()
```

- [ ] **Step 2: Run tests (regression check)**

Run: `uv run pytest -v`
Expected: all tests PASS

- [ ] **Step 3: Boot and verify profiles come from the DB**

Run:

```bash
./stop.sh; ./start.sh; sleep 6
curl -s -c /tmp/cl-cookies.txt -X POST http://localhost:8890/login \
  -d "username=admin&password=root123_" -o /dev/null -w "login %{http_code}\n"
curl -s -b /tmp/cl-cookies.txt http://localhost:8890/project/settings \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([p['name'] for p in d['chatProfiles']])"
```

Expected: `login 200` then `['General', 'Dryback', 'Crystal']`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "Drive chat profiles from projects table with General default"
```

---

### Task 4: ProjectDashboard custom element

**Files:**
- Create: `public/elements/ProjectDashboard.jsx`

**Interfaces:**
- Consumes: `props` = `{"name": str | null, "description": str, "files": [{"name": str, "size": int}]}` (Task 3's `_dashboard_props`); Chainlit globals `props` and `callAction`.
- Produces: `callAction({name: "create_project", payload: {name, description}})` and `callAction({name: "add_project_files", payload: {}})` — handled by Task 5.

- [ ] **Step 1: Write the component**

Create `public/elements/ProjectDashboard.jsx`:

```jsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FileText, FolderOpen, FolderPlus, Upload } from "lucide-react";

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProjectDashboard() {
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const submitNewProject = () => {
    if (!newName.trim()) return;
    callAction({
      name: "create_project",
      payload: { name: newName.trim(), description: newDescription.trim() },
    });
    setShowForm(false);
    setNewName("");
    setNewDescription("");
  };

  return (
    <Card className="max-w-md border-purple-300 dark:border-purple-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5 text-purple-500" />
          {props.name ? `Project: ${props.name}` : "No project selected"}
        </CardTitle>
        <CardDescription>
          {props.name
            ? props.description || "No description yet."
            : "Pick a project from the profile dropdown, or create a new one."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {props.name && (
          <div>
            <p className="text-sm font-medium mb-1">
              Shared files ({props.files.length})
            </p>
            {props.files.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No files attached to this project yet.
              </p>
            ) : (
              <ul className="space-y-1">
                {props.files.map((file) => (
                  <li
                    key={file.name}
                    className="flex items-center gap-2 text-sm"
                  >
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">{file.name}</span>
                    <span className="ml-auto text-muted-foreground">
                      {formatSize(file.size)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {showForm && (
          <div className="space-y-2 rounded-md border p-3">
            <Input
              placeholder="Project name (e.g. Dryback)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Textarea
              placeholder="Business context: what the client does, location, size…"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={submitNewProject}>
                Create
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex gap-2">
        {props.name && (
          <Button
            size="sm"
            onClick={() => callAction({ name: "add_project_files", payload: {} })}
          >
            <Upload className="h-4 w-4 mr-1" /> Add files
          </Button>
        )}
        {!showForm && (
          <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
            <FolderPlus className="h-4 w-4 mr-1" /> New project
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
```

- [ ] **Step 2: Restart and visually verify rendering**

Run: `./stop.sh; ./start.sh; sleep 6`

Open `http://localhost:8890`, log in (`admin` / password from `.env`). Verify:
- Default profile is **General**; first message shows the dashboard card in its "No project selected" state with a working "New project" form toggle.
- Switch profile to **Dryback** (confirm-new-chat dialog appears): card shows "Project: Dryback", empty file list, "Add files" + "New project" buttons.
- Clicking buttons will error until Task 5 defines the callbacks — that is expected at this point.

- [ ] **Step 3: Commit**

```bash
git add public/elements/ProjectDashboard.jsx
git commit -m "Add ProjectDashboard custom element"
```

---

### Task 5: Action callbacks — create project, attach files

**Files:**
- Modify: `main.py` (append after `on_chat_resume`)

**Interfaces:**
- Consumes: `callAction` payloads from Task 4; `cl.user_session["project"]` and `cl.user_session["dashboard_el"]` from Task 3; `projects.create_project`, `projects.add_project_file` from Task 1.
- Produces: user-visible confirmation messages; refreshed dashboard props via `CustomElement.update()`.

- [ ] **Step 1: Add the action callbacks**

Append to `main.py`:

```python
@cl.action_callback("create_project")
async def on_create_project(action: cl.Action):
    name = (action.payload.get("name") or "").strip()
    description = (action.payload.get("description") or "").strip()
    try:
        project = projects.create_project(name, description)
    except ValueError as exc:
        await cl.Message(content=f"Could not create project: {exc}").send()
        return
    await cl.Message(
        content=(
            f"Project **{project['name']}** created. "
            "Refresh the page and pick it from the profile dropdown to start working in it."
        )
    ).send()


@cl.action_callback("add_project_files")
async def on_add_project_files(action: cl.Action):
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(
            content="No active project. Pick one from the profile dropdown first."
        ).send()
        return

    replies = await cl.AskFileMessage(
        content=f"Upload files to attach to **{project['name']}**.",
        accept=["*/*"],
        max_files=20,
        max_size_mb=100,
    ).send()
    if not replies:
        return

    for reply in replies:
        projects.add_project_file(
            project["id"], reply.name, reply.path, reply.type, reply.size
        )

    # On resumed threads the session has no dashboard element (on_chat_resume
    # doesn't send one), so fall back to sending a fresh dashboard message.
    dashboard = cl.user_session.get("dashboard_el")
    if dashboard:
        dashboard.props = _dashboard_props(project)
        await dashboard.update()
    else:
        await _send_dashboard(project, f"Updated files for **{project['name']}**:")

    names = ", ".join(reply.name for reply in replies)
    await cl.Message(
        content=f"Attached {len(replies)} file(s) to **{project['name']}**: {names}"
    ).send()
```

- [ ] **Step 2: Run tests (regression check)**

Run: `uv run pytest -v`
Expected: all tests PASS

- [ ] **Step 3: End-to-end verification in the browser**

Run: `./stop.sh; ./start.sh; sleep 6`, open `http://localhost:8890`, log in, then:

1. Profile **Dryback** → send "cash flow question" → sidebar shows thread named `[Dryback] cash flow question` (may need a sidebar refresh).
2. Click **Add files** on the dashboard → upload any small PDF → confirmation message appears AND the dashboard card's file list updates in place; `project_files/<id>/<name>` exists on disk.
3. Click **New project** → create name `TestCo`, description `A test client` → confirmation message; after a page refresh the profile dropdown shows **TestCo**.
4. Switch to profile **General** → send "hello" → thread appears in the sidebar WITHOUT a `[...]` prefix; static response still returned.
5. Type `dryback` in the sidebar search → only the `[Dryback]` thread matches.
6. Click the old `[Dryback]` thread to resume it → click **Add files** → upload works and a fresh dashboard message with the updated file list appears (proves `on_chat_resume` restored the project and the no-`dashboard_el` fallback works).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "Add create-project and attach-files actions"
```

---

### Task 6: Documentation + final review

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: everything above.
- Produces: docs matching reality.

- [ ] **Step 1: Update `CLAUDE.md`**

In the **Architecture & Key Concepts** section, update the Backend bullet list: `main.py` now only wires callbacks; add bullets for `projects.py` (project/file repository, `GENERAL_PROFILE`) and `data_layer.py` (`ProjectDataLayer`: SQLite-safe tags, `[Project] ` prefixes, name-aware search). In **Code Structure & File Locations**, add rows for `projects.py`, `data_layer.py`, `public/elements/ProjectDashboard.jsx`, and `project_files/` (gitignored runtime dir). In **Testing**, replace the "No automated test suite" paragraph with: `uv run pytest` runs the suite in `tests/`; single test: `uv run pytest tests/test_projects.py::test_create_and_get_project -v`.

- [ ] **Step 2: Update `AGENTS.md`**

Apply the same corrections to the Project Structure paragraph (mention `projects.py`, `data_layer.py`, `project_files/`) and the Testing Guidelines section (pytest now configured; keep the manual checklist and add: verify project switching via profile dropdown, `[Project]` thread prefixes, and project file attach flow).

- [ ] **Step 3: Full regression + boot check**

Run: `uv run pytest -v && ./stop.sh; ./start.sh; sleep 6; tail -3 chainlit.log`
Expected: all tests PASS; app boots cleanly.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "Document project mode architecture and test commands"
```

---

## Known Limitations (accepted in design review 2026-07-14)

- New projects appear in the profile dropdown only after a page refresh (Chainlit fetches profiles once per settings load).
- The sidebar shows all threads across projects, distinguished by `[Project] ` name prefixes and filterable via search — not collapsible folders (that would require `custom_build`, out of scope).
- `on_message` remains the static response; project files/description are persisted and available in `cl.user_session["project"]` for future LLM integration but are not yet fed to a model.
- Attaching two project files with the same filename overwrites on disk and duplicates in the listing — acceptable for the 2-3 client scale; revisit if it bites.
