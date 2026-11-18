"""Tests for claims_graph.py."""
from schema import RoutingDecision

import claims_graph
import router
from claims_graph import build_graph


def test_fan_out_only_runs_routed_specialists(monkeypatch):
    """Monkeypatch router.route_claim to force a billing-only decision, run
    the compiled graph on a fake state, and assert tool_results contains
    ONLY the "billing" key -- proving the fan-out genuinely skips unrouted
    specialists, with no live OpenRouter call.
    """

    def fake_route_claim(claim_text: str) -> RoutingDecision:
        return RoutingDecision(
            specialists=["billing"],
            reason="fixed decision for fan-out test",
            confidence=0.99,
        )

    monkeypatch.setattr(router, "route_claim", fake_route_claim)

    graph = build_graph()
    result = graph.invoke(
        {
            "claim_id": "FAKE-CLM",
            "claim_text": "irrelevant -- router is monkeypatched",
            "order_id": "FAKE-ORDER-ID-NOT-IN-CSV",
        }
    )

    assert set(result["tool_results"].keys()) == {"billing"}
    assert "shipping" not in result["tool_results"]
    assert "stock" not in result["tool_results"]
