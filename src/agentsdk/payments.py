"""Payments primitive — wallet, transfers, escrow, spending limits."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import aiosqlite


@dataclass
class PaymentsPrimitive:
    agent_id: str
    db_path: str
    _db: aiosqlite.Connection | None = None
    spending_limits: dict[str, float] = field(default_factory=dict)

    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS wallets (
                    agent_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    balance REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (agent_id, currency)
                )"""
            )
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT,
                    to_agent TEXT,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL,
                    metadata TEXT
                )"""
            )
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS escrows (
                    id TEXT PRIMARY KEY,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'held',
                    created_at REAL
                )"""
            )
            await self._db.commit()
        return self._db

    async def balance(self, currency: str = "USD") -> float:
        db = await self._conn()
        async with db.execute(
            "SELECT balance FROM wallets WHERE agent_id=? AND currency=?",
            (self.agent_id, currency),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0.0

    async def deposit(self, amount: float, currency: str = "USD") -> str:
        db = await self._conn()
        await db.execute(
            """INSERT INTO wallets (agent_id, currency, balance) VALUES (?, ?, ?)
               ON CONFLICT(agent_id, currency) DO UPDATE SET balance = balance + ?""",
            (self.agent_id, currency, amount, amount),
        )
        tx_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO transactions VALUES (?, NULL, ?, ?, ?, 'completed', ?, NULL)",
            (tx_id, self.agent_id, amount, currency, time.time()),
        )
        await db.commit()
        return tx_id

    async def pay(self, to_agent: str, amount: float, currency: str = "USD", metadata: dict | None = None) -> str:
        limit = self.spending_limits.get(currency)
        if limit is not None and amount > limit:
            raise ValueError(f"Amount {amount} exceeds spending limit {limit} {currency}")
        db = await self._conn()
        bal = await self.balance(currency)
        if bal < amount:
            raise ValueError(f"Insufficient balance: {bal} < {amount} {currency}")
        tx_id = str(uuid.uuid4())
        await db.execute(
            "UPDATE wallets SET balance = balance - ? WHERE agent_id=? AND currency=?",
            (amount, self.agent_id, currency),
        )
        await db.execute(
            """INSERT INTO wallets (agent_id, currency, balance) VALUES (?, ?, ?)
               ON CONFLICT(agent_id, currency) DO UPDATE SET balance = balance + ?""",
            (to_agent, currency, amount, amount),
        )
        await db.execute(
            "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, 'completed', ?, ?)",
            (tx_id, self.agent_id, to_agent, amount, currency, time.time(), json.dumps(metadata) if metadata else None),
        )
        await db.commit()
        return tx_id

    async def escrow(self, to_agent: str, amount: float, currency: str = "USD") -> str:
        db = await self._conn()
        bal = await self.balance(currency)
        if bal < amount:
            raise ValueError(f"Insufficient balance for escrow: {bal} < {amount}")
        esc_id = str(uuid.uuid4())
        await db.execute(
            "UPDATE wallets SET balance = balance - ? WHERE agent_id=? AND currency=?",
            (amount, self.agent_id, currency),
        )
        await db.execute(
            "INSERT INTO escrows VALUES (?, ?, ?, ?, ?, 'held', ?)",
            (esc_id, self.agent_id, to_agent, amount, currency, time.time()),
        )
        await db.commit()
        return esc_id

    async def release_escrow(self, escrow_id: str) -> bool:
        db = await self._conn()
        async with db.execute("SELECT * FROM escrows WHERE id=? AND status='held'", (escrow_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        _, from_agent, to_agent, amount, currency, _, _ = row
        await db.execute(
            """INSERT INTO wallets (agent_id, currency, balance) VALUES (?, ?, ?)
               ON CONFLICT(agent_id, currency) DO UPDATE SET balance = balance + ?""",
            (to_agent, currency, amount, amount),
        )
        await db.execute("UPDATE escrows SET status='released' WHERE id=?", (escrow_id,))
        await db.commit()
        return True

    async def set_spending_limit(self, currency: str, limit: float) -> None:
        self.spending_limits[currency] = limit

    async def transaction_history(self, limit: int = 50) -> list[dict[str, Any]]:
        db = await self._conn()
        rows = []
        async with db.execute(
            "SELECT * FROM transactions WHERE from_agent=? OR to_agent=? ORDER BY created_at DESC LIMIT ?",
            (self.agent_id, self.agent_id, limit),
        ) as cur:
            async for r in cur:
                rows.append({"id": r[0], "from": r[1], "to": r[2], "amount": r[3], "currency": r[4], "status": r[5]})
        return rows

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
