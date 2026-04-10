"""Observability primitive — OpenTelemetry-compatible traces and cost tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter


@dataclass
class ObservabilityPrimitive:
    agent_id: str
    _costs: list[dict[str, Any]] = field(default_factory=list)
    _tracer: trace.Tracer = field(init=False, repr=False)

    def __post_init__(self):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        self._tracer = provider.get_tracer(f"agentsdk.{self.agent_id}")

    def span(self, name: str, attributes: dict[str, Any] | None = None):
        """Return a context-manager span."""
        span = self._tracer.start_span(name, attributes=attributes or {})
        return _SpanCtx(span)

    def track_cost(self, operation: str, amount: float, currency: str = "USD", metadata: dict | None = None):
        self._costs.append({
            "operation": operation,
            "amount": amount,
            "currency": currency,
            "timestamp": time.time(),
            "metadata": metadata,
        })

    def total_cost(self, currency: str = "USD") -> float:
        return sum(c["amount"] for c in self._costs if c["currency"] == currency)

    def cost_report(self) -> list[dict[str, Any]]:
        return list(self._costs)


class _SpanCtx:
    def __init__(self, span):
        self._span = span

    def __enter__(self):
        return self._span

    def __exit__(self, *args):
        self._span.end()
