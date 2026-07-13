-- SQLite schema for chainlit.data.sql_alchemy.SQLAlchemyDataLayer.
-- Column names are reverse-engineered from the literal INSERT/SELECT
-- statements in chainlit/data/sql_alchemy.py (chainlit==2.11.1), not guessed.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    identifier TEXT UNIQUE NOT NULL,
    createdAt TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    createdAt TEXT,
    name TEXT,
    userId TEXT REFERENCES users(id),
    userIdentifier TEXT,
    tags TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    threadId TEXT REFERENCES threads(id),
    parentId TEXT,
    command TEXT,
    modes TEXT,
    streaming INTEGER,
    waitForAnswer INTEGER,
    isError INTEGER,
    metadata TEXT,
    tags TEXT,
    input TEXT,
    output TEXT,
    createdAt TEXT,
    start TEXT,
    end TEXT,
    generation TEXT,
    showInput TEXT,
    defaultOpen INTEGER,
    autoCollapse INTEGER,
    language TEXT,
    icon TEXT
);

CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    threadId TEXT REFERENCES threads(id),
    type TEXT,
    chainlitKey TEXT,
    path TEXT,
    url TEXT,
    objectKey TEXT,
    name TEXT,
    display TEXT,
    size TEXT,
    language TEXT,
    page INTEGER,
    props TEXT,
    autoPlay INTEGER,
    playerConfig TEXT,
    forId TEXT,
    mime TEXT
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id TEXT PRIMARY KEY,
    forId TEXT NOT NULL,
    threadId TEXT NOT NULL REFERENCES threads(id),
    value INTEGER NOT NULL,
    comment TEXT
);
