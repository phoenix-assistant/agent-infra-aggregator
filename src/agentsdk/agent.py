"""Agent — top-level façade that wires together all primitives."""

from __future__ import annotations

import os
from typing import Any, Sequence

from agentsdk.identity import IdentityPrimitive
from agentsdk.memory import MemoryPrimitive
from agentsdk.payments import PaymentsPrimitive
from agentsdk.comms import CommsPrimitive
from agentsdk.observability import ObservabilityPrimitive


class Agent:
    """Unified agent with pluggable primitives."""

    def __init__(
        self,
        id: str,
        capabilities: Sequence[str] | None = None,
        db_path: str | None = None,
    ):
        self.id = id
        caps = set(capabilities or ["identity", "memory", "payments", "comms", "observability"])
        _db = db_path or os.path.join(os.getcwd(), f".agentsdk_{id}.db")

        self.identity = IdentityPrimitive(agent_id=id) if "identity" in caps else None
        self.memory = MemoryPrimitive(db_path=_db) if "memory" in caps else None
        self.wallet = PaymentsPrimitive(agent_id=id, db_path=_db) if "payments" in caps else None
        self.comms = CommsPrimitive(agent_id=id, db_path=_db) if "comms" in caps else None
        self.observability = ObservabilityPrimitive(agent_id=id) if "observability" in caps else None

    # convenience shortcut
    async def send(self, recipient: str, message: dict[str, Any]) -> str:
        if not self.comms:
            raise RuntimeError("comms not enabled")
        return await self.comms.send(self.id, recipient, message)

    async def close(self):
        if self.memory:
            await self.memory.close()
        if self.wallet:
            await self.wallet.close()
        if self.comms:
            await self.comms.close()
