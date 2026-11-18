"""Specialist tools: look up order lines for billing/shipping/stock claims.

Each tool reads fresh from the order-line-records CSV on every call (no
caching, no hardcoded data) and never raises just because an order_id is
absent from that file -- that is the expected, correct outcome whenever a
tool is called against one of the 15 labeled refund claims, since those
claims' order_ids have zero overlap with the order-line-records file.
"""
import csv
from pathlib import Path

from pydantic import BaseModel

from schema import Specialist

ORDER_LINES_PATH = Path(__file__).parent / "Amazon Order Line Records: Payment, Tracking and Stock.csv"


class ToolResult(BaseModel):
    specialist: Specialist
    order_id: str
    found: bool
    rows: list[dict[str, str]]
    note: str


def _load_order_lines(order_id: str) -> list[dict[str, str]]:
    """Read the order-line-records CSV fresh and return rows matching order_id.

    Lets FileNotFoundError propagate naturally if the CSV itself is missing.
    """
    with open(ORDER_LINES_PATH, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row["order_id"] == order_id]


def _run_tool(specialist: Specialist, order_id: str) -> ToolResult:
    rows = _load_order_lines(order_id)
    if not rows:
        return ToolResult(
            specialist=specialist,
            order_id=order_id,
            found=False,
            rows=[],
            note=f"no record found for order_id {order_id!r} in the order-line-records file",
        )
    return ToolResult(specialist=specialist, order_id=order_id, found=True, rows=rows, note="")


def billing_tool(order_id: str) -> ToolResult:
    return _run_tool("billing", order_id)


def shipping_tool(order_id: str) -> ToolResult:
    return _run_tool("shipping", order_id)


def stock_tool(order_id: str) -> ToolResult:
    return _run_tool("stock", order_id)
