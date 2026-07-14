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
