import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SessionKey = tuple[str, int, int | None]

DATABASE_PATH = Path("data") / "chat_memory.db"
MAX_LONG_TERM_MEMORY_CHARS = 1200


class LongTermMemoryStore:
    """基于 SQLite 的会话长期记忆摘要存储。"""

    def __init__(self, database_path: Path, use_wal: bool = True):
        self.database_path = database_path
        self.use_wal = use_wal
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                if self.use_wal:
                    connection.execute("PRAGMA journal_mode = WAL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_memory (
                        scope_type TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        group_id INTEGER NOT NULL,
                        summary TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (scope_type, user_id, group_id)
                    )
                    """
                )

    async def initialize(self) -> None:
        if self._initialized:
            return
        await asyncio.to_thread(self._initialize)
        self._initialized = True

    @staticmethod
    def _row_key(session_key: SessionKey) -> tuple[str, int, int]:
        scope_type, user_id, group_id = session_key
        return scope_type, user_id, group_id or 0

    def _get_summary(self, session_key: SessionKey) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT summary
                FROM chat_memory
                WHERE scope_type = ? AND user_id = ? AND group_id = ?
                """,
                self._row_key(session_key),
            ).fetchone()
        return str(row["summary"]) if row else ""

    async def get_summary(self, session_key: SessionKey) -> str:
        await self.initialize()
        return await asyncio.to_thread(self._get_summary, session_key)

    def _upsert_summary(self, session_key: SessionKey, summary: str) -> None:
        normalized = normalize_memory_summary(summary)
        updated_at = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO chat_memory (
                        scope_type, user_id, group_id, summary, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(scope_type, user_id, group_id) DO UPDATE SET
                        summary = excluded.summary,
                        updated_at = excluded.updated_at
                    """,
                    (*self._row_key(session_key), normalized, updated_at),
                )

    async def upsert_summary(self, session_key: SessionKey, summary: str) -> None:
        await self.initialize()
        await asyncio.to_thread(self._upsert_summary, session_key, summary)

    def _delete_summary(self, session_key: SessionKey) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    DELETE FROM chat_memory
                    WHERE scope_type = ? AND user_id = ? AND group_id = ?
                    """,
                    self._row_key(session_key),
                )
        return cursor.rowcount > 0

    async def delete_summary(self, session_key: SessionKey) -> bool:
        await self.initialize()
        return await asyncio.to_thread(self._delete_summary, session_key)


memory_store = LongTermMemoryStore(DATABASE_PATH)


def normalize_memory_summary(summary: str) -> str:
    normalized_lines = [
        line.strip()
        for line in str(summary).splitlines()
        if line.strip()
    ]
    normalized = "\n".join(normalized_lines)
    return normalized[:MAX_LONG_TERM_MEMORY_CHARS]


def build_long_term_memory_prompt(summary: str) -> str:
    normalized = normalize_memory_summary(summary)
    if not normalized:
        return ""

    return (
        "\n当前会话的长期记忆摘要：\n"
        f"{normalized}\n"
        "这些记忆只属于当前会话的当前发言用户，可用于称呼、偏好、长期目标和近期重要事项；"
        "它不是最新消息。若与当前发言冲突，以当前发言为准。"
        "不要把摘要里的信息归因给其他人。"
    )


def trim_history_for_memory(
    history: list[dict[str, Any]],
    max_messages: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(history) <= max_messages:
        return history, []

    overflow_count = len(history) - max_messages
    return history[overflow_count:], history[:overflow_count]


def format_messages_for_memory(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            text = content.strip()
        else:
            text = str(content).strip()
        if text:
            lines.append(f"用户: {text}")
    return "\n".join(lines)
