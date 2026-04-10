# AgentSDK

Unified SDK giving AI agents identity, memory, payments, and communication primitives. One import, five superpowers.

## Install

```bash
pip install agentsdk
```

## Quickstart

```python
import asyncio
from agentsdk import Agent

async def main():
    agent = Agent(id="agent-123", capabilities=["memory", "payments", "comms"])

    # Memory — remember and recall anything
    await agent.memory.remember("user-pref", {"theme": "dark"})
    prefs = await agent.memory.recall("user-pref")
    print(prefs)  # {"theme": "dark"}

    # Semantic search
    results = await agent.memory.search("user preferences")

    # Payments — deposit, pay, escrow
    await agent.wallet.deposit(500.0)
    await agent.wallet.pay("vendor-456", amount=50, currency="USD")
    print(await agent.wallet.balance())  # 450.0

    # Escrow
    escrow_id = await agent.wallet.escrow("vendor-456", 100.0)
    await agent.wallet.release_escrow(escrow_id)

    # Comms — agent-to-agent messaging
    await agent.send("agent-789", {"type": "task", "payload": "do stuff"})
    inbox = await agent.comms.inbox()

    # Identity — PKI signing
    signed = await agent.identity.sign("important message")
    verified = await agent.identity.verify("important message", signed)

    # Observability — cost tracking
    agent.observability.track_cost("llm-call", 0.05)
    print(agent.observability.total_cost())  # 0.05

    await agent.close()

asyncio.run(main())
```

## Primitives

### Identity
Ed25519 key pair per agent. Sign/verify messages, DID generation.

```python
agent.identity.did          # "did:key:z..."
await agent.identity.sign("msg")
await agent.identity.verify("msg", signature)
```

### Memory
SQLite-backed key-value store with local vector search (numpy, no external services).

```python
await agent.memory.remember("key", {"any": "value"})
await agent.memory.recall("key")
await agent.memory.search("semantic query", top_k=5)
await agent.memory.forget("key")
```

### Payments
Wallet with deposits, transfers, escrow, and spending limits.

```python
await agent.wallet.deposit(100.0, currency="USD")
await agent.wallet.pay("other-agent", amount=50.0)
await agent.wallet.escrow("vendor", 200.0)
await agent.wallet.set_spending_limit("USD", 500.0)
await agent.wallet.transaction_history()
```

### Comms
Agent-to-agent messaging with inbox/outbox and read tracking.

```python
await agent.send("recipient-id", {"type": "request", "data": ...})
await agent.comms.inbox(unread_only=True)
await agent.comms.outbox()
await agent.comms.mark_read(message_id)
```

### Observability
OpenTelemetry-compatible tracing and cost tracking.

```python
with agent.observability.span("operation-name"):
    ...  # traced
agent.observability.track_cost("llm-call", 0.03)
agent.observability.total_cost()  # cumulative
```

## MCP Server

Expose all primitives as MCP tools:

```bash
agentsdk-mcp  # stdio transport
```

Tools: `memory_remember`, `memory_recall`, `memory_search`, `identity_sign`, `identity_verify`, `wallet_balance`, `wallet_pay`, `comms_send`, `comms_inbox`

## Stack

- **Python 3.10+** — zero external service dependencies
- **SQLite** — all persistence (aiosqlite)
- **numpy** — local vector embeddings
- **cryptography** — Ed25519 PKI
- **OpenTelemetry** — traces and spans
- **MCP** — model context protocol server

## License

MIT
