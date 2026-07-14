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


def test_create_reserved_name_raises(db_path):
    with pytest.raises(ValueError, match="reserved"):
        projects.create_project("General", db_path=db_path)


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
