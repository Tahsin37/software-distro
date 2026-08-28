"""
SQLite database layer with async support and auto-migration.
"""
import aiosqlite
import json
import time
from pathlib import Path
from typing import Optional, Any
from config import settings

DB_PATH = str(settings.database_path)

MIGRATIONS = [
    # Migration 0: Initial schema
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at REAL NOT NULL,
        started_at REAL,
        completed_at REAL,
        error TEXT,
        result TEXT,
        metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS task_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        data TEXT DEFAULT '{}',
        timestamp REAL NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS tool_calls (
        id TEXT PRIMARY KEY,
        task_id TEXT,
        tool_name TEXT NOT NULL,
        input TEXT NOT NULL,
        output TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        started_at REAL NOT NULL,
        completed_at REAL,
        duration_ms REAL,
        error TEXT,
        retry_count INTEGER DEFAULT 0,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        UNIQUE(category, key)
    );

    CREATE TABLE IF NOT EXISTS settings_store (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sandboxes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'stopped',
        root_path TEXT,
        created_at REAL NOT NULL,
        config TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tool_calls TEXT,
        timestamp REAL NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE INDEX IF NOT EXISTS idx_task_events_task_id ON task_events(task_id);
    CREATE INDEX IF NOT EXISTS idx_tool_calls_task_id ON tool_calls(task_id);
    CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id);
    CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category);
    """,
]


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database and run migrations."""
    db = await get_db()
    try:
        # Check current version
        await db.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        cursor = await db.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        current_version = row[0] if row[0] is not None else -1

        # Run pending migrations
        for i, migration in enumerate(MIGRATIONS):
            if i > current_version:
                for statement in migration.split(";"):
                    statement = statement.strip()
                    if statement:
                        await db.execute(statement)
                await db.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (i,)
                )

        await db.commit()
    finally:
        await db.close()


class Database:
    """Async database helper."""

    @staticmethod
    async def execute(query: str, params: tuple = ()) -> Any:
        db = await get_db()
        try:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor
        finally:
            await db.close()

    @staticmethod
    async def fetch_one(query: str, params: tuple = ()) -> Optional[dict]:
        db = await get_db()
        try:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            await db.close()

    @staticmethod
    async def fetch_all(query: str, params: tuple = ()) -> list[dict]:
        db = await get_db()
        try:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await db.close()

    @staticmethod
    async def insert(table: str, data: dict) -> str:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        await Database.execute(query, tuple(data.values()))
        return data.get("id", "")

    @staticmethod
    async def update(table: str, data: dict, where: str, params: tuple = ()) -> None:
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        await Database.execute(query, tuple(data.values()) + params)
