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
