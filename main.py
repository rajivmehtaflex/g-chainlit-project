import asyncio
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import chainlit as cl
from chainlit.types import ThreadDict
from chainlit.input_widget import TextInput
from chainlit.data import get_data_layer as get_active_data_layer

import projects
from app_logging import logger
from data_layer import ProjectDataLayer
from projects import GENERAL_PROFILE

load_dotenv()

# Project files are persisted in project_files/ (see projects.py), not via a
# Chainlit blob storage client, so the per-upload element-persistence warning is
# expected noise. Filter just that one message; all other chainlit logs remain.
logging.getLogger("chainlit").addFilter(
    lambda r: "No blob_storage_client is configured" not in r.getMessage()
)

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "chainlit.db"
SCHEMA_PATH = APP_DIR / "schema.sql"

SEED_PROJECTS = ["Dryback", "Crystal"]

UPLOAD_MAX_MB = 200          # Add-files cap; project knowledge files (PDF/XLSX) rarely exceed this
UPLOAD_TIMEOUT_S = 300       # explicit, generous window for selecting/uploading up to 20 files


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
        logger.info("login succeeded username={}", username)
        return cl.User(identifier=username, metadata={"role": "ADMIN"})
    logger.warning("login failed username={}", username)
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
    logger.debug(
        "chat_profiles listed user={} count={}",
        current_user.identifier if current_user else None, len(profiles),
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
    logger.info("dashboard sent project={}", project["name"] if project else "None (General)")


async def _refresh_dashboard(project: dict, fallback_greeting: str) -> None:
    dashboard = cl.user_session.get("dashboard_el")
    if dashboard:
        dashboard.props = _dashboard_props(project)
        await dashboard.update()
        logger.info("dashboard refreshed in place project={}", project["name"])
    else:
        await _send_dashboard(project, fallback_greeting)
        logger.warning(
            "dashboard_el missing in session; sent fallback dashboard project={}",
            project["name"],
        )


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
    logger.info(
        "chat_start user={} profile={} project={}",
        user.identifier, profile, project["name"] if project else GENERAL_PROFILE,
    )
    if project:
        greeting = f"Hello {user.identifier}! Project **{project['name']}** is active."
    else:
        greeting = f"Hello {user.identifier}! How can I help you today?"
    await _send_dashboard(project, greeting)
    await _project_settings().send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    user = cl.user_session.get("user")
    tags = thread.get("tags") or []
    project = None
    for tag in tags:
        if tag != GENERAL_PROFILE:
            project = projects.get_project(tag)
            if project:
                break
    cl.user_session.set("project", project)
    logger.info(
        "chat_resume user={} thread_id={} tags={} project={}",
        user.identifier, thread.get("id"), tags, project["name"] if project else GENERAL_PROFILE,
    )
    if project:
        greeting = f"Welcome back, {user.identifier}! Project **{project['name']}** is active."
    else:
        greeting = f"Welcome back, {user.identifier}!"
    await _send_dashboard(project, greeting)
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
        logger.warning("project creation failed name={} reason={}", name, exc)
        await cl.Message(content=f"Could not create project: {exc}").send()
        return
    logger.info("project created name={} id={}", project["name"], project["id"])

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
    logger.debug("message received length={}", len(message.content or ""))
    await cl.Message(content=os.environ["STATIC_RESPONSE"]).send()


@cl.action_callback("add_project_files")
async def on_add_project_files(action: cl.Action):
    logger.info("action_callback invoked name={} id={}", action.name, action.id)
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(
            content="No active project. Pick one from the profile dropdown first."
        ).send()
        return

    logger.info("upload requested project={}", project["name"])
    replies = await cl.AskFileMessage(
        content=f"Upload files to attach to **{project['name']}**.",
        accept=["*/*"],
        max_files=20,
        max_size_mb=UPLOAD_MAX_MB,
        timeout=UPLOAD_TIMEOUT_S,
    ).send()
    if not replies:
        logger.warning(
            "upload timed out or cancelled project={} timeout_s={}",
            project["name"], UPLOAD_TIMEOUT_S,
        )
        await cl.Message(
            content=(
                "No files received — the upload window timed out or was cancelled. "
                "Click **Add files** on the project card to try again."
            )
        ).send()
        return

    saving = cl.Message(content=f"Saving {len(replies)} file(s) to **{project['name']}**…")
    await saving.send()
    logger.info("upload batch started files={} project={}", len(replies), project["name"])
    batch_start = time.perf_counter()
    # shutil.copy2 + sqlite writes are blocking; run them off the event loop so
    # large/many-file uploads don't freeze the app. Each add_project_file opens
    # its own connection, so per-file threading is safe; sequential await avoids
    # SQLite write-lock contention.
    for reply in replies:
        file_start = time.perf_counter()
        await asyncio.to_thread(
            projects.add_project_file,
            project["id"], reply.name, reply.path, reply.type, reply.size,
        )
        logger.info(
            "file copied name={} duration_ms={}",
            reply.name, round((time.perf_counter() - file_start) * 1000, 1),
        )
    logger.info(
        "upload batch completed files={} total_duration_ms={} project={}",
        len(replies), round((time.perf_counter() - batch_start) * 1000, 1), project["name"],
    )

    await _refresh_dashboard(project, f"Updated files for **{project['name']}**:")

    names = ", ".join(reply.name for reply in replies)
    saving.content = f"Attached {len(replies)} file(s) to **{project['name']}**: {names}"
    await saving.update()


@cl.action_callback("update_project_description")
async def on_update_project_description(action: cl.Action):
    logger.info("action_callback invoked name={} id={}", action.name, action.id)
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

    await _refresh_dashboard(updated, f"Updated description for **{updated['name']}**:")


@cl.action_callback("delete_project")
async def on_delete_project(action: cl.Action):
    logger.info("action_callback invoked name={} id={}", action.name, action.id)
    project = cl.user_session.get("project")
    if not project:
        await cl.Message(content="No active project.").send()
        return

    confirm_name = (action.payload.get("confirm_name") or "").strip()
    if confirm_name != project["name"]:
        logger.warning(
            "delete_project confirmation mismatch project={} typed={}",
            project["name"], confirm_name,
        )
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
    logger.info(
        "project deleted name={} id={} cascaded_threads={}",
        project["name"], project["id"], deleted_threads,
    )
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
    logger.info("action_callback invoked name={} id={}", action.name, action.id)
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

    await _refresh_dashboard(project, f"Renamed a file in **{project['name']}**:")


@cl.action_callback("delete_project_file")
async def on_delete_project_file(action: cl.Action):
    logger.info("action_callback invoked name={} id={}", action.name, action.id)
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

    await _refresh_dashboard(project, f"Removed a file from **{project['name']}**:")
