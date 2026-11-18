"""Tests for claims_graph.py."""
from schema import RoutingDecision

import router
from claims_graph import (
    CONFIDENCE_ESCALATION_THRESHOLD,
    build_graph,
    contradicts_billing,
    contradicts_shipping,
    contradicts_stock,
    low_confidence,
    missing_record,
)

# NOTE: the row dicts below are synthetic fixtures, not real
# order-line-records data. The real 15 labeled claims can never exercise
# these contradiction branches because their order_ids have zero overlap
# with the order-line-records file, so finding["found"] is always False
# for them -- these unit tests exist to exercise the branches directly.


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


def test_low_confidence_below_threshold():
    assert low_confidence(0.69) is True


def test_low_confidence_at_threshold_is_not_low():
    assert low_confidence(CONFIDENCE_ESCALATION_THRESHOLD) is False


def test_low_confidence_above_threshold():
    assert low_confidence(0.95) is False


def test_missing_record_true_when_any_specialist_not_found():
    tool_results = {
        "billing": {"found": True},
        "shipping": {"found": False},
    }
    assert missing_record(["billing", "shipping"], tool_results) is True


def test_missing_record_false_when_all_found():
    tool_results = {
        "billing": {"found": True},
        "shipping": {"found": True},
    }
    assert missing_record(["billing", "shipping"], tool_results) is False


def test_contradicts_billing_true_when_all_matched_rows_single_charge():
    claim_text = "I was charged twice for my order and want a refund."
    finding = {
        "found": True,
        "rows": [
            {"charge_count": "1"},
            {"charge_count": "1"},
        ],
    }
    assert contradicts_billing(claim_text, finding) is True


def test_contradicts_billing_false_when_a_row_actually_double_charged():
    claim_text = "I was charged twice for my order and want a refund."
    finding = {
        "found": True,
        "rows": [
            {"charge_count": "2"},
            {"charge_count": "1"},
        ],
    }
    assert contradicts_billing(claim_text, finding) is False


def test_contradicts_billing_false_when_claim_text_does_not_mention_duplicate_charge():
    claim_text = "My item never arrived."
    finding = {"found": True, "rows": [{"charge_count": "1"}]}
    assert contradicts_billing(claim_text, finding) is False


def test_contradicts_billing_false_when_not_found():
    claim_text = "I was charged twice for my order."
    finding = {"found": False, "rows": []}
    assert contradicts_billing(claim_text, finding) is False


def test_contradicts_shipping_true_when_marked_delivered_with_date():
    claim_text = "My package never arrived, I need a refund."
    finding = {
        "found": True,
        "rows": [
            {"package_status": "Delivered", "delivered_date": "2025-06-02"},
        ],
    }
    assert contradicts_shipping(claim_text, finding) is True


def test_contradicts_shipping_false_when_no_row_delivered():
    claim_text = "My package never arrived, I need a refund."
    finding = {
        "found": True,
        "rows": [
            {"package_status": "In Transit", "delivered_date": ""},
        ],
    }
    assert contradicts_shipping(claim_text, finding) is False


def test_contradicts_shipping_false_when_claim_text_not_about_non_delivery():
    claim_text = "I was double charge for this order."
    finding = {
        "found": True,
        "rows": [{"package_status": "Delivered", "delivered_date": "2025-06-02"}],
    }
    assert contradicts_shipping(claim_text, finding) is False


def test_contradicts_stock_true_when_a_matched_row_is_in_stock():
    claim_text = "The seller said this item is out of stock but I still need it."
    finding = {
        "found": True,
        "rows": [{"stock_status": "In Stock"}],
    }
    assert contradicts_stock(claim_text, finding) is True


def test_contradicts_stock_false_when_all_rows_out_of_stock():
    claim_text = "The seller said this item is out of stock but I still need it."
    finding = {
        "found": True,
        "rows": [{"stock_status": "Out of Stock"}],
    }
    assert contradicts_stock(claim_text, finding) is False


def test_contradicts_stock_false_when_claim_text_not_about_unavailability():
    claim_text = "My package never arrived."
    finding = {
        "found": True,
        "rows": [{"stock_status": "In Stock"}],
    }
    assert contradicts_stock(claim_text, finding) is False
