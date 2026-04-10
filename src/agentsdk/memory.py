"""Memory primitive — short/long-term storage with semantic vector search."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import aiosqlite
import numpy as np


def _embed(text: str) -> np.ndarray:
    """Deterministic bag-of-chars embedding (no external model needed)."""
    vec = np.zeros(128, dtype=np.float32)
    for i, ch in enumerate(text.encode("utf-8")):
        vec[ch % 128] += 1.0 / (1 + i * 0.01)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


@dataclass
class MemoryPrimitive:
    db_path: str
    _db: aiosqlite.Connection | None = None

    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    embedding BLOB,
                    created_at REAL,
                    accessed_at REAL
                )"""
            )
            await self._db.commit()
        return self._db

    async def remember(self, key: str, value: Any) -> None:
        db = await self._conn()
        val_str = json.dumps(value) if not isinstance(value, str) else value
        emb = _embed(f"{key} {val_str}").tobytes()
        now = time.time()
        await db.execute(
            "INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?)",
            (key, val_str, emb, now, now),
        )
        await db.commit()

    async def recall(self, key: str) -> Any | None:
        db = await self._conn()
        now = time.time()
        await db.execute("UPDATE memories SET accessed_at=? WHERE key=?", (now, key))
        await db.commit()
        async with db.execute("SELECT value FROM memories WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return row[0]

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        db = await self._conn()
        q_emb = _embed(query)
        results: list[tuple[float, str, str]] = []
        async with db.execute("SELECT key, value, embedding FROM memories") as cur:
            async for key, value, emb_blob in cur:
                if emb_blob:
                    emb = np.frombuffer(emb_blob, dtype=np.float32)
                    score = _cosine(q_emb, emb)
                    results.append((score, key, value))
        results.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, key, value in results[:top_k]:
            try:
                v = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                v = value
            out.append({"key": key, "value": v, "score": round(score, 4)})
        return out

    async def forget(self, key: str) -> bool:
        db = await self._conn()
        cur = await db.execute("DELETE FROM memories WHERE key=?", (key,))
        await db.commit()
        return cur.rowcount > 0

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
