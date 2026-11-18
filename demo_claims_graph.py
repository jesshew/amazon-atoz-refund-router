"""Live, printed demo of the claims graph against 3 real labeled claims,
chosen because their label_specialists need different specialist
combinations:

  - CLM-0002: billing only
  - CLM-0013: shipping | stock
  - CLM-0001: billing | shipping | stock

This makes 3 real OpenRouter calls (one route_claim per claim) -- that is
expected and fine.

Every specialist tool call against these claims is expected to come back
found=False, because the 15 labeled claims' order_ids have zero overlap
with the order-line-records CSV's order_ids (confirmed by direct
set-diff). That is printed honestly below, not suppressed.
"""
from claims_graph import build_graph
from router import load_claim

DEMO_CLAIM_IDS = ["CLM-0002", "CLM-0013", "CLM-0001"]


def main() -> None:
    graph = build_graph()

    for claim_id in DEMO_CLAIM_IDS:
        claim = load_claim(claim_id)

        print("\n" + "#" * 72)
        print(f"# CLAIM {claim_id}  (order_id: {claim['order_id']})")
        print("#" * 72)
        print(f"claim_text: {claim['claim_text']}")
        print(f"label_specialists (ground truth): {claim['label_specialists']}")

        result = graph.invoke(
            {
                "claim_id": claim["claim_id"],
                "claim_text": claim["claim_text"],
                "order_id": claim["order_id"],
            }
        )

        routing = result["routing"]
        print("\n-- router decision --")
        print(f"  specialists: {routing['specialists']}")
        print(f"  reason: {routing['reason']}")
        print(f"  confidence: {routing['confidence']}")

        tool_results = result["tool_results"]
        print(f"\n-- specialist tool calls made ({len(tool_results)} of 3 possible) --")
        for specialist, tool_result in tool_results.items():
            print(f"  [{specialist}] found={tool_result['found']} rows={len(tool_result['rows'])} note={tool_result['note'] or '(none)'}")

        resolution = result["resolution"]
        print("\n-- final ClaimResolution --")
        print(f"  specialists_consulted: {resolution['specialists_consulted']}")
        print(f"  router_confidence: {resolution['router_confidence']}")
        print(f"  escalation: {resolution['escalation']}")
        print(f"  escalate_to_human: {resolution['escalate_to_human']}")
        print(f"  human_review_reason: {resolution['human_review_reason']}")

        final_status = result["final_status"]
        print(f"\n-- final_status --")
        print(f"  status: {final_status['status']}")
        print(f"  reviewed_by: {final_status['reviewed_by']}")


if __name__ == "__main__":
    main()
