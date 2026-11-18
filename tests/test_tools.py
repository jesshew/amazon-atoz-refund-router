"""Tests for tools.py specialist lookups.

Negative-path coverage: all 15 labeled claims against all 3 tools. This is
expected to always be found=False because the labeled claims' order_ids and
the order-line-records file's order_ids have zero overlap (confirmed by
direct set-diff) -- that is correct, not a bug.

Positive-path coverage: one real order-line-records order_id per tool,
proving a tool doesn't just always return "not found" regardless of input.
"""
import csv
from pathlib import Path

import pytest

from router import load_claim
from tools import billing_tool, shipping_tool, stock_tool

LABELED_CLAIMS_PATH = Path(__file__).parent.parent / "data" / "Labeled Amazon A-to-z Refund Claims (15-claim test set).csv"
ORDER_LINES_PATH = Path(__file__).parent.parent / "Amazon Order Line Records: Payment, Tracking and Stock.csv"

TOOLS = [billing_tool, shipping_tool, stock_tool]


def _all_claim_ids() -> list[str]:
    with open(LABELED_CLAIMS_PATH, newline="", encoding="utf-8") as f:
        return [row["claim_id"] for row in csv.DictReader(f)]


# A real order_id taken directly from the order-line-records CSV (first data
# row) -- intentionally one of the 15 real order-line-records ids, not a
# labeled-claim order_id, so this exercises the found=True path.
with open(ORDER_LINES_PATH, newline="", encoding="utf-8") as _f:
    REAL_ORDER_ID = next(csv.DictReader(_f))["order_id"]


@pytest.mark.parametrize("claim_id", _all_claim_ids())
@pytest.mark.parametrize("tool", TOOLS, ids=[t.__name__ for t in TOOLS])
def test_tool_finds_no_record_for_labeled_claim_order_ids(claim_id, tool):
    claim = load_claim(claim_id)
    result = tool(claim["order_id"])
    assert result.found is False
    assert result.rows == []
    assert result.note != ""


def test_billing_tool_finds_real_order():
    result = billing_tool(REAL_ORDER_ID)
    assert result.found is True
    assert len(result.rows) > 0


def test_shipping_tool_finds_real_order():
    result = shipping_tool(REAL_ORDER_ID)
    assert result.found is True
    assert len(result.rows) > 0


def test_stock_tool_finds_real_order():
    result = stock_tool(REAL_ORDER_ID)
    assert result.found is True
    assert len(result.rows) > 0
