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


def test_add_project_file_rejects_path_traversal(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"%PDF-fake")

    rec = projects.add_project_file(
        project["id"], "../evil.txt", str(source), "text/plain", 9,
        db_path=db_path, files_dir=files_dir,
    )
    stored = Path(rec["path"])
    assert stored.parent == files_dir / project["id"]
    assert stored.name == "evil.txt"

    with pytest.raises(ValueError, match="Invalid file name"):
        projects.add_project_file(
            project["id"], "..", str(source), "text/plain", 9,
            db_path=db_path, files_dir=files_dir,
        )


def test_ensure_seed_projects_idempotent(db_path):
    projects.ensure_seed_projects(["Dryback", "Crystal"], db_path=db_path)
    projects.ensure_seed_projects(["Dryback", "Crystal"], db_path=db_path)
    assert len(projects.list_projects(db_path=db_path)) == 2


def test_update_project_description(db_path):
    project = projects.create_project("Dryback", "old description", db_path=db_path)
    updated = projects.update_project_description(
        project["id"], "new description", db_path=db_path
    )
    assert updated["description"] == "new description"
    assert updated["name"] == "Dryback"

    fetched = projects.get_project("Dryback", db_path=db_path)
    assert fetched["description"] == "new description"


def test_update_project_description_strips_whitespace(db_path):
    project = projects.create_project("Dryback", db_path=db_path)
    updated = projects.update_project_description(project["id"], "  padded  ", db_path=db_path)
    assert updated["description"] == "padded"


def test_update_project_description_missing_project_raises(db_path):
    with pytest.raises(ValueError, match="No project"):
        projects.update_project_description("nonexistent-id", "x", db_path=db_path)


def test_delete_project_removes_row_files_and_directory(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"%PDF-fake")
    projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 9,
        db_path=db_path, files_dir=files_dir,
    )
    project_dir = files_dir / project["id"]
    assert project_dir.exists()

    projects.delete_project(project["id"], db_path=db_path, files_dir=files_dir)

    assert projects.get_project("Dryback", db_path=db_path) is None
    assert projects.list_project_files(project["id"], db_path=db_path) == []
    assert not project_dir.exists()


def test_delete_project_missing_project_is_noop(db_path, files_dir):
    projects.delete_project("nonexistent-id", db_path=db_path, files_dir=files_dir)


def test_get_project_file_returns_record(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"data")
    rec = projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )
    assert projects.get_project_file(rec["id"], db_path=db_path) == rec


def test_get_project_file_missing_returns_none(db_path):
    assert projects.get_project_file("nonexistent-id", db_path=db_path) is None


def test_rename_project_file(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"data")
    rec = projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )

    renamed = projects.rename_project_file(
        rec["id"], "final-report.pdf", db_path=db_path, files_dir=files_dir
    )

    assert renamed["name"] == "final-report.pdf"
    new_path = Path(renamed["path"])
    assert new_path.exists()
    assert new_path.name == "final-report.pdf"
    assert not (files_dir / project["id"] / "report.pdf").exists()

    listed = projects.list_project_files(project["id"], db_path=db_path)
    assert [f["name"] for f in listed] == ["final-report.pdf"]


def test_rename_project_file_rejects_path_traversal(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"data")
    rec = projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )
    with pytest.raises(ValueError, match="Invalid file name"):
        projects.rename_project_file(rec["id"], "../evil.txt", db_path=db_path, files_dir=files_dir)


def test_rename_project_file_rejects_duplicate_name(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"data")
    projects.add_project_file(
        project["id"], "a.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )
    rec_b = projects.add_project_file(
        project["id"], "b.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )
    with pytest.raises(ValueError, match="already exists"):
        projects.rename_project_file(rec_b["id"], "a.pdf", db_path=db_path, files_dir=files_dir)


def test_rename_project_file_missing_raises(db_path, files_dir):
    with pytest.raises(ValueError, match="No file"):
        projects.rename_project_file("nonexistent-id", "new.pdf", db_path=db_path, files_dir=files_dir)


def test_delete_project_file_removes_row_and_disk_file(db_path, files_dir, tmp_path):
    project = projects.create_project("Dryback", db_path=db_path)
    source = tmp_path / "upload.pdf"
    source.write_bytes(b"data")
    rec = projects.add_project_file(
        project["id"], "report.pdf", str(source), "application/pdf", 4,
        db_path=db_path, files_dir=files_dir,
    )
    stored = Path(rec["path"])
    assert stored.exists()

    projects.delete_project_file(rec["id"], db_path=db_path)

    assert projects.get_project_file(rec["id"], db_path=db_path) is None
    assert not stored.exists()


def test_delete_project_file_missing_is_noop(db_path):
    projects.delete_project_file("nonexistent-id", db_path=db_path)
