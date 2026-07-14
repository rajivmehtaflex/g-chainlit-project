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


def update_project_description(
    project_id: str, description: str, db_path: Optional[Path] = None
) -> dict:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE projects SET description = ? WHERE id = ?",
            (description.strip(), project_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"No project with id '{project_id}'")
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    finally:
        conn.close()
    return dict(row)


def delete_project(
    project_id: str, db_path: Optional[Path] = None, files_dir: Optional[Path] = None
) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM project_files WHERE projectId = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()
    shutil.rmtree((files_dir or PROJECT_FILES_DIR) / project_id, ignore_errors=True)


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
    name = Path(name).name
    if name in ("", ".", ".."):
        raise ValueError("Invalid file name")
    dest = dest_dir / name
    if not dest.resolve().is_relative_to(dest_dir.resolve()):
        raise ValueError("Invalid file name")
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


def get_project_file(file_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM project_files WHERE id = ?", (file_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def rename_project_file(
    file_id: str,
    new_name: str,
    db_path: Optional[Path] = None,
    files_dir: Optional[Path] = None,
) -> dict:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM project_files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No file with id '{file_id}'")
        record = dict(row)

        # Unlike upload (which silently basenames), a rename is a deliberate
        # single-target action, so reject anything that isn't already a bare
        # filename rather than quietly transforming it.
        if new_name != Path(new_name).name or new_name in ("", ".", ".."):
            raise ValueError("Invalid file name")

        dest_dir = (files_dir or PROJECT_FILES_DIR) / record["projectId"]
        new_path = dest_dir / new_name
        if not new_path.resolve().is_relative_to(dest_dir.resolve()):
            raise ValueError("Invalid file name")

        if new_name != record["name"]:
            collision = conn.execute(
                "SELECT 1 FROM project_files WHERE projectId = ? AND name = ? AND id != ?",
                (record["projectId"], new_name, file_id),
            ).fetchone()
            if collision:
                raise ValueError(
                    f"A file named '{new_name}' already exists in this project"
                )

        old_path = Path(record["path"])
        if old_path.exists():
            old_path.rename(new_path)

        conn.execute(
            "UPDATE project_files SET name = ?, path = ? WHERE id = ?",
            (new_name, str(new_path), file_id),
        )
        conn.commit()
        record["name"] = new_name
        record["path"] = str(new_path)
    finally:
        conn.close()
    return record


def delete_project_file(file_id: str, db_path: Optional[Path] = None) -> None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT path FROM project_files WHERE id = ?", (file_id,)
        ).fetchone()
        conn.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
        conn.commit()
    finally:
        conn.close()
    if row:
        Path(row["path"]).unlink(missing_ok=True)


def ensure_seed_projects(names: list[str], db_path: Optional[Path] = None) -> None:
    for name in names:
        if get_project(name, db_path=db_path) is None:
            create_project(name, db_path=db_path)
