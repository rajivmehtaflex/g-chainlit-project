import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import chainlit as cl
from chainlit.types import ThreadDict
from chainlit.input_widget import TextInput
from chainlit.data import get_data_layer as get_active_data_layer

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
        "files": [{"id": f["id"], "name": f["name"], "size": f["size"]} for f in files],
    }


async def _send_dashboard(project: Optional[dict], greeting: str) -> None:
    props = _dashboard_props(project) if project else {"name": None, "description": "", "files": []}
    dashboard = cl.CustomElement(name="ProjectDashboard", props=props)
    cl.user_session.set("dashboard_el", dashboard)
    await cl.Message(content=greeting, elements=[dashboard]).send()


async def _resolve_user_id(user: Optional[cl.User]) -> Optional[str]:
    """Get a PersistedUser id even if session.user somehow isn't persisted yet.

    Mirrors the same defensive check chainlit/server.py uses at the
    /project/threads endpoint (isinstance(current_user, PersistedUser)) rather
    than assuming cl.user_session["user"] always has .id.
    """
    if isinstance(user, cl.PersistedUser):
        return user.id
    data_layer = get_active_data_layer()
    if not user or not data_layer:
        return None
    persisted = await data_layer.get_user(identifier=user.identifier)
    return persisted.id if persisted else None


def _project_settings() -> cl.ChatSettings:
    return cl.ChatSettings(
        inputs=[
            TextInput(
                id="new_project_name",
                label="New project name",
                initial="",
                placeholder="e.g. Acme Corp",
            ),
            TextInput(
                id="new_project_description",
                label="New project description",
                initial="",
                placeholder="Business context: what the client does, location, size…",
                multiline=True,
            ),
        ]
    )


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
    await _project_settings().send()


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
    await _project_settings().send()


@cl.on_settings_update
async def on_settings_update(settings: dict):
    name = (settings.get("new_project_name") or "").strip()
    if not name:
        return
    description = (settings.get("new_project_description") or "").strip()
    try:
        project = projects.create_project(name, description)
    except ValueError as exc:
        await cl.Message(content=f"Could not create project: {exc}").send()
        return

    await _project_settings().send()  # reset the fields blank for the next entry
    await cl.Message(
        content=f"Project **{project['name']}** created.",
        elements=[
            cl.CustomElement(
                name="ReloadPrompt",
                props={
                    "message": (
                        f"Reload the page to see {project['name']} "
                        "in the profile dropdown."
                    )
                },
            )
        ],
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    await cl.Message(content=os.environ["STATIC_RESPONSE"]).send()


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


@cl.action_callback("update_project_description")
async def on_update_project_description(action: cl.Action):
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(content="No active project.").send()
        return

    description = (action.payload.get("description") or "").strip()
    try:
        updated = projects.update_project_description(project["id"], description)
    except ValueError as exc:
        await cl.Message(content=f"Could not update description: {exc}").send()
        return
    cl.user_session.set("project", updated)

    dashboard = cl.user_session.get("dashboard_el")
    if dashboard:
        dashboard.props = _dashboard_props(updated)
        await dashboard.update()
    else:
        await _send_dashboard(updated, f"Updated description for **{updated['name']}**:")


@cl.action_callback("delete_project")
async def on_delete_project(action: cl.Action):
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(content="No active project.").send()
        return

    confirm_name = (action.payload.get("confirm_name") or "").strip()
    if confirm_name != project["name"]:
        await cl.Message(
            content=f"Type the project name exactly (**{project['name']}**) to confirm deletion."
        ).send()
        return

    deleted_threads = 0
    data_layer = get_active_data_layer()
    if data_layer:
        user_id = await _resolve_user_id(cl.user_session.get("user"))
        if user_id:
            threads = await data_layer.get_all_user_threads(user_id=user_id) or []
            for thread in threads:
                if project["name"] in (thread.get("tags") or []):
                    await data_layer.delete_thread(thread["id"])
                    deleted_threads += 1

    projects.delete_project(project["id"])
    cl.user_session.set("project", None)
    cl.user_session.set("dashboard_el", None)

    await cl.Message(
        content=(
            f"Project **{project['name']}** deleted, along with "
            f"{deleted_threads} thread(s)."
        ),
        elements=[
            cl.CustomElement(
                name="ReloadPrompt",
                props={
                    "message": (
                        "Reload the page to update the profile dropdown and thread list."
                    )
                },
            )
        ],
    ).send()


@cl.action_callback("rename_project_file")
async def on_rename_project_file(action: cl.Action):
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(content="No active project.").send()
        return

    file_id = action.payload.get("file_id") or ""
    new_name = (action.payload.get("new_name") or "").strip()
    file_record = projects.get_project_file(file_id)
    if not file_record or file_record["projectId"] != project["id"]:
        await cl.Message(content="File not found in this project.").send()
        return

    try:
        projects.rename_project_file(file_id, new_name)
    except ValueError as exc:
        await cl.Message(content=f"Could not rename file: {exc}").send()
        return

    dashboard = cl.user_session.get("dashboard_el")
    if dashboard:
        dashboard.props = _dashboard_props(project)
        await dashboard.update()
    else:
        await _send_dashboard(project, f"Renamed a file in **{project['name']}**:")


@cl.action_callback("delete_project_file")
async def on_delete_project_file(action: cl.Action):
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(content="No active project.").send()
        return

    file_id = action.payload.get("file_id") or ""
    file_record = projects.get_project_file(file_id)
    if not file_record or file_record["projectId"] != project["id"]:
        await cl.Message(content="File not found in this project.").send()
        return

    projects.delete_project_file(file_id)

    dashboard = cl.user_session.get("dashboard_el")
    if dashboard:
        dashboard.props = _dashboard_props(project)
        await dashboard.update()
    else:
        await _send_dashboard(project, f"Removed a file from **{project['name']}**:")
