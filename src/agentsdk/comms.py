"""Comms primitive — agent-to-agent messaging with inbox/outbox."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass
class CommsPrimitive:
    agent_id: str
    db_path: str
    _db: aiosqlite.Connection | None = None

    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'sent',
                    created_at REAL,
                    read_at REAL
                )"""
            )
            await self._db.commit()
        return self._db

    async def send(self, from_agent: str, to_agent: str, message: dict[str, Any]) -> str:
        db = await self._conn()
        msg_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, 'sent', ?, NULL)",
            (msg_id, from_agent, to_agent, json.dumps(message), time.time()),
        )
        await db.commit()
        return msg_id

    async def inbox(self, limit: int = 50, unread_only: bool = False) -> list[dict[str, Any]]:
        db = await self._conn()
        q = "SELECT * FROM messages WHERE to_agent=?"
        params: list[Any] = [self.agent_id]
        if unread_only:
            q += " AND read_at IS NULL"
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = []
        async with db.execute(q, params) as cur:
            async for r in cur:
                payload = json.loads(r[3]) if r[3] else {}
                rows.append({"id": r[0], "from": r[1], "to": r[2], "payload": payload, "status": r[4], "created_at": r[5]})
        return rows

    async def outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        db = await self._conn()
        rows = []
        async with db.execute(
            "SELECT * FROM messages WHERE from_agent=? ORDER BY created_at DESC LIMIT ?",
            (self.agent_id, limit),
        ) as cur:
            async for r in cur:
                payload = json.loads(r[3]) if r[3] else {}
                rows.append({"id": r[0], "from": r[1], "to": r[2], "payload": payload, "status": r[4], "created_at": r[5]})
        return rows

    async def mark_read(self, message_id: str) -> bool:
        db = await self._conn()
        cur = await db.execute(
            "UPDATE messages SET read_at=?, status='read' WHERE id=? AND to_agent=?",
            (time.time(), message_id, self.agent_id),
        )
        await db.commit()
        return cur.rowcount > 0

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
