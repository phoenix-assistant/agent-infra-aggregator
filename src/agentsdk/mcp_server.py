"""MCP server exposing AgentSDK primitives."""

from __future__ import annotations

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from agentsdk import Agent

_agent: Agent | None = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(id="mcp-agent", db_path="/tmp/agentsdk_mcp.db")
    return _agent


def create_server() -> Server:
    server = Server("agentsdk")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name="memory_remember", description="Store a key-value pair in agent memory",
                 inputSchema={"type": "object", "properties": {"key": {"type": "string"}, "value": {}}, "required": ["key", "value"]}),
            Tool(name="memory_recall", description="Recall a value by key",
                 inputSchema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}),
            Tool(name="memory_search", description="Semantic search over memories",
                 inputSchema={"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]}),
            Tool(name="identity_sign", description="Sign a message",
                 inputSchema={"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}),
            Tool(name="identity_verify", description="Verify a signature",
                 inputSchema={"type": "object", "properties": {"message": {"type": "string"}, "signature": {"type": "string"}}, "required": ["message", "signature"]}),
            Tool(name="wallet_balance", description="Get wallet balance",
                 inputSchema={"type": "object", "properties": {"currency": {"type": "string"}}}),
            Tool(name="wallet_pay", description="Pay another agent",
                 inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "amount": {"type": "number"}, "currency": {"type": "string"}}, "required": ["to", "amount"]}),
            Tool(name="comms_send", description="Send message to another agent",
                 inputSchema={"type": "object", "properties": {"to": {"type": "string"}, "message": {}}, "required": ["to", "message"]}),
            Tool(name="comms_inbox", description="Read inbox",
                 inputSchema={"type": "object", "properties": {"limit": {"type": "integer"}}}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        agent = _get_agent()
        result: object = None

        if name == "memory_remember":
            await agent.memory.remember(arguments["key"], arguments["value"])
            result = {"status": "stored"}
        elif name == "memory_recall":
            result = await agent.memory.recall(arguments["key"])
        elif name == "memory_search":
            result = await agent.memory.search(arguments["query"], arguments.get("top_k", 5))
        elif name == "identity_sign":
            sig = await agent.identity.sign(arguments["message"])
            result = {"signature": sig, "did": agent.identity.did}
        elif name == "identity_verify":
            ok = await agent.identity.verify(arguments["message"], arguments["signature"])
            result = {"verified": ok}
        elif name == "wallet_balance":
            bal = await agent.wallet.balance(arguments.get("currency", "USD"))
            result = {"balance": bal}
        elif name == "wallet_pay":
            tx_id = await agent.wallet.pay(arguments["to"], arguments["amount"], arguments.get("currency", "USD"))
            result = {"transaction_id": tx_id}
        elif name == "comms_send":
            msg_id = await agent.comms.send(agent.id, arguments["to"], arguments["message"])
            result = {"message_id": msg_id}
        elif name == "comms_inbox":
            result = await agent.comms.inbox(arguments.get("limit", 50))
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def main():
    server = create_server()
    asyncio.run(_run(server))


async def _run(server: Server):
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
