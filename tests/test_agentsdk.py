"""Tests for all AgentSDK primitives."""

import os
import tempfile
import pytest
from agentsdk import Agent


@pytest.fixture
async def agent(tmp_path):
    db = str(tmp_path / "test.db")
    a = Agent(id="test-agent", db_path=db)
    yield a
    await a.close()


@pytest.fixture
async def agent_b(tmp_path):
    db = str(tmp_path / "test.db")
    a = Agent(id="agent-b", db_path=db)
    yield a
    await a.close()


# --- Identity ---

async def test_identity_did(agent):
    assert agent.identity.did.startswith("did:key:z")


async def test_identity_sign_verify(agent):
    sig = await agent.identity.sign("hello world")
    assert isinstance(sig, str)
    assert await agent.identity.verify("hello world", sig)


async def test_identity_verify_wrong_message(agent):
    sig = await agent.identity.sign("hello")
    assert not await agent.identity.verify("wrong", sig)


# --- Memory ---

async def test_memory_remember_recall(agent):
    await agent.memory.remember("pref", {"theme": "dark"})
    result = await agent.memory.recall("pref")
    assert result == {"theme": "dark"}


async def test_memory_recall_missing(agent):
    result = await agent.memory.recall("nonexistent")
    assert result is None


async def test_memory_search(agent):
    await agent.memory.remember("color", "blue")
    await agent.memory.remember("food", "pizza")
    results = await agent.memory.search("color blue")
    assert len(results) > 0
    assert results[0]["key"] == "color"


async def test_memory_forget(agent):
    await agent.memory.remember("temp", "data")
    assert await agent.memory.forget("temp")
    assert await agent.memory.recall("temp") is None


# --- Payments ---

async def test_wallet_deposit_balance(agent):
    await agent.wallet.deposit(100.0)
    bal = await agent.wallet.balance()
    assert bal == 100.0


async def test_wallet_pay(agent):
    await agent.wallet.deposit(200.0)
    tx_id = await agent.wallet.pay("vendor-1", amount=50.0)
    assert tx_id
    bal = await agent.wallet.balance()
    assert bal == 150.0


async def test_wallet_insufficient_funds(agent):
    with pytest.raises(ValueError, match="Insufficient"):
        await agent.wallet.pay("vendor-1", amount=999.0)


async def test_wallet_spending_limit(agent):
    await agent.wallet.deposit(1000.0)
    await agent.wallet.set_spending_limit("USD", 100.0)
    with pytest.raises(ValueError, match="spending limit"):
        await agent.wallet.pay("vendor-1", amount=200.0)


async def test_wallet_escrow(agent):
    await agent.wallet.deposit(500.0)
    esc_id = await agent.wallet.escrow("vendor-1", 200.0)
    assert await agent.wallet.balance() == 300.0
    assert await agent.wallet.release_escrow(esc_id)


async def test_wallet_transaction_history(agent):
    await agent.wallet.deposit(100.0)
    await agent.wallet.pay("v1", 10.0)
    history = await agent.wallet.transaction_history()
    assert len(history) >= 2


# --- Comms ---

async def test_comms_send_inbox(agent):
    msg_id = await agent.send("agent-b", {"type": "hello"})
    assert msg_id
    # Check outbox
    outbox = await agent.comms.outbox()
    assert len(outbox) == 1


async def test_comms_mark_read(tmp_path):
    db = str(tmp_path / "comms.db")
    a = Agent(id="a", db_path=db)
    b = Agent(id="b", db_path=db)
    msg_id = await a.send("b", {"text": "hi"})
    inbox = await b.comms.inbox(unread_only=True)
    assert len(inbox) == 1
    assert await b.comms.mark_read(msg_id)
    inbox2 = await b.comms.inbox(unread_only=True)
    assert len(inbox2) == 0
    await a.close()
    await b.close()


# --- Observability ---

async def test_observability_cost_tracking(agent):
    agent.observability.track_cost("llm-call", 0.05)
    agent.observability.track_cost("llm-call", 0.03)
    assert agent.observability.total_cost() == pytest.approx(0.08)


async def test_observability_span(agent):
    with agent.observability.span("test-op", {"key": "val"}) as span:
        assert span is not None


async def test_observability_cost_report(agent):
    agent.observability.track_cost("embed", 0.01)
    report = agent.observability.cost_report()
    assert len(report) == 1
    assert report[0]["operation"] == "embed"


# --- Agent convenience ---

async def test_agent_selective_capabilities(tmp_path):
    db = str(tmp_path / "sel.db")
    a = Agent(id="minimal", capabilities=["memory"], db_path=db)
    assert a.memory is not None
    assert a.wallet is None
    assert a.comms is None
    await a.close()
