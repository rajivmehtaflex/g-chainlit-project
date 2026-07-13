import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.types import ThreadDict

load_dotenv()

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "chainlit.db"
SCHEMA_PATH = APP_DIR / "schema.sql"


def _init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()


_init_db()


@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo=f"sqlite+aiosqlite:///{DB_PATH}")


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if (
        username == os.environ["CHAINLIT_AUTH_USERNAME"]
        and password == os.environ["CHAINLIT_AUTH_PASSWORD"]
    ):
        return cl.User(identifier=username, metadata={"role": "ADMIN"})
    return None


@cl.on_chat_start
async def on_chat_start():
    user = cl.user_session.get("user")
    welcome_card = cl.CustomElement(
        name="WelcomeCard",
        props={
            "title": "G-Chainlit Assistant",
            "description": f"Hello {user.identifier}! This is a demo custom UI component.",
        },
    )
    await cl.Message(
        content=f"Hello {user.identifier}! How can I help you today?",
        elements=[welcome_card],
    ).send()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    pass


@cl.on_message
async def on_message(message: cl.Message):
    await cl.Message(content=os.environ["STATIC_RESPONSE"]).send()
