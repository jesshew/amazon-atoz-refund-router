"""LangGraph pipeline: route a claim, fan out to the specialist tools the
router picked, merge their findings into a ClaimResolution, then hand off
to a (simulated) human-review step.

Fan-out: route_to_specialists returns a list[str] of node names from the
conditional edge function. Verified empirically (see scratchpad probe) on
the installed langgraph version that this fans out to all listed nodes in
one superstep, that unrouted specialist nodes do not run, and that
merge_node runs exactly once, after all fanned-out specialist nodes finish
-- this relies on tool_results being Annotated[dict, operator.or_] so the
Pregel engine has a reducer for the same-superstep concurrent writes.
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

import router
import tools
from schema import ClaimResolution, EscalationFlags, SpecialistFinding

CONFIDENCE_ESCALATION_THRESHOLD = 0.70

SPECIALIST_NODE_NAMES = {
    "billing": "billing_node",
    "shipping": "shipping_node",
    "stock": "stock_node",
}


class ClaimState(TypedDict, total=False):
    claim_id: str
    claim_text: str
    order_id: str
    routing: dict
    tool_results: Annotated[dict, operator.or_]
    resolution: dict
    final_status: dict


def router_node(state: ClaimState) -> dict:
    decision = router.route_claim(state["claim_text"])
    return {"routing": decision.model_dump()}


def billing_node(state: ClaimState) -> dict:
    result = tools.billing_tool(state["order_id"])
    return {"tool_results": {"billing": result.model_dump()}}


def shipping_node(state: ClaimState) -> dict:
    result = tools.shipping_tool(state["order_id"])
    return {"tool_results": {"shipping": result.model_dump()}}


def stock_node(state: ClaimState) -> dict:
    result = tools.stock_tool(state["order_id"])
    return {"tool_results": {"stock": result.model_dump()}}


def route_to_specialists(state: ClaimState) -> list[str]:
    """Fan-out function: maps routed specialists to their node names."""
    return [SPECIALIST_NODE_NAMES[s] for s in state["routing"]["specialists"]]


# --- escalation condition helpers (each independently unit-testable) ---


def missing_record(specialists: list[str], tool_results: dict) -> bool:
    return any(not tool_results[s]["found"] for s in specialists)


def low_confidence(confidence: float) -> bool:
    return confidence < CONFIDENCE_ESCALATION_THRESHOLD


DUPLICATE_CHARGE_PHRASES = ["charged twice", "two charges", "double charge", "duplicate charge"]
NON_DELIVERY_PHRASES = [
    "never arrived",
    "nothing arrived",
    "never reached",
    "did not arrive",
    "never showed up",
    "never turned up",
]
UNAVAILABILITY_PHRASES = [
    "out of stock",
    "sold out",
    "no longer available",
    "unavailable",
    "backorder",
    "oversold",
]


def contradicts_billing(claim_text: str, finding: dict) -> bool:
    """True if the claim alleges a duplicate charge but every matched
    order line shows charge_count <= 1 (i.e. nothing actually double-charged).
    """
    if not finding.get("found"):
        return False
    text = claim_text.lower()
    if not any(phrase in text for phrase in DUPLICATE_CHARGE_PHRASES):
        return False
    rows = finding["rows"]
    if not rows:
        return False
    return all(int(row["charge_count"]) <= 1 for row in rows)


def contradicts_shipping(claim_text: str, finding: dict) -> bool:
    """True if the claim alleges non-delivery but some matched order line
    is marked Delivered with a non-empty delivered_date.
    """
    if not finding.get("found"):
        return False
    text = claim_text.lower()
    if not any(phrase in text for phrase in NON_DELIVERY_PHRASES):
        return False
    rows = finding["rows"]
    return any(
        row["package_status"] == "Delivered" and bool(row.get("delivered_date"))
        for row in rows
    )


def contradicts_stock(claim_text: str, finding: dict) -> bool:
    """True if the claim alleges unavailability but some matched order
    line shows stock_status == "In Stock".
    """
    if not finding.get("found"):
        return False
    text = claim_text.lower()
    if not any(phrase in text for phrase in UNAVAILABILITY_PHRASES):
        return False
    rows = finding["rows"]
    return any(row["stock_status"] == "In Stock" for row in rows)


def merge_node(state: ClaimState) -> dict:
    routing = state["routing"]
    tool_results = state["tool_results"]
    specialists = routing["specialists"]

    findings = {s: SpecialistFinding(**tool_results[s]) for s in specialists}

    mr = missing_record(specialists, tool_results)
    lc = low_confidence(routing["confidence"])
    cb = contradicts_billing(state["claim_text"], tool_results.get("billing", {}))
    cs = contradicts_shipping(state["claim_text"], tool_results.get("shipping", {}))
    cst = contradicts_stock(state["claim_text"], tool_results.get("stock", {}))

    reasons = []
    if mr:
        missing = [s for s in specialists if not tool_results[s]["found"]]
        reasons.append(
            f"no record found for: {', '.join(missing)} "
            f"(order_id {state['order_id']} not present in order-line-records file)"
        )
    if lc:
        reasons.append(
            f"router confidence {routing['confidence']:.2f} below "
            f"{CONFIDENCE_ESCALATION_THRESHOLD:.2f} threshold"
        )
    if cb:
        reasons.append(
            "billing record contradicts claimed duplicate charge "
            "(all matched lines show charge_count <= 1)"
        )
    if cs:
        reasons.append(
            "shipping record contradicts claimed non-delivery "
            "(a matched line is marked Delivered with a delivered_date)"
        )
    if cst:
        reasons.append(
            "stock record contradicts claimed unavailability "
            "(a matched line shows stock_status In Stock)"
        )

    escalate_to_human = mr or lc or cb or cs or cst
    human_review_reason = "; ".join(reasons) if reasons else "no escalation conditions met"

    resolution = ClaimResolution(
        claim_id=state["claim_id"],
        order_id=state["order_id"],
        specialists_consulted=specialists,
        findings=findings,
        router_confidence=routing["confidence"],
        escalation=EscalationFlags(
            missing_record=mr,
            low_confidence=lc,
            contradicts_billing=cb,
            contradicts_shipping=cs,
            contradicts_stock=cst,
        ),
        escalate_to_human=escalate_to_human,
        human_review_reason=human_review_reason,
    )
    return {"resolution": resolution.model_dump()}


def human_review_node(state: ClaimState) -> dict:
    resolution = state["resolution"]
    status = "pending_human_review" if resolution["escalate_to_human"] else "auto_resolved"

    print("=" * 72)
    print(f"HUMAN REVIEW -- claim_id: {resolution['claim_id']}")
    print(f"status: {status}")
    print(f"reason: {resolution['human_review_reason']}")
    for specialist, finding in resolution["findings"].items():
        print(f"  [{specialist}] found={finding['found']} note={finding['note'] or '(none)'}")
    print("=" * 72)

    return {
        "final_status": {
            "status": status,
            "reviewed_by": "human_review_node (simulated -- no human in this exercise)",
        }
    }


def build_graph():
    graph = StateGraph(ClaimState)
    graph.add_node("router_node", router_node)
    graph.add_node("billing_node", billing_node)
    graph.add_node("shipping_node", shipping_node)
    graph.add_node("stock_node", stock_node)
    graph.add_node("merge_node", merge_node)
    graph.add_node("human_review_node", human_review_node)

    graph.set_entry_point("router_node")
    graph.add_conditional_edges(
        "router_node",
        route_to_specialists,
        ["billing_node", "shipping_node", "stock_node"],
    )
    graph.add_edge("billing_node", "merge_node")
    graph.add_edge("shipping_node", "merge_node")
    graph.add_edge("stock_node", "merge_node")
    graph.add_edge("merge_node", "human_review_node")
    graph.add_edge("human_review_node", END)

    return graph.compile()
