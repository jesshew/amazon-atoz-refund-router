"""Router: classifies an Amazon A-to-z refund claim into one or more
specialists (billing, shipping, stock) by asking an OpenRouter model for
structured output, then validating the reply against RoutingDecision.

Usage:
    python router.py                  # runs claim 1 from the test set
    python router.py --claim-id CLM-0007
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from schema import RoutingDecision

DATA_PATH = Path(__file__).parent / "data" / "Labeled Amazon A-to-z Refund Claims (15-claim test set).csv"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a routing classifier for Amazon A-to-z Guarantee refund claims.
Read only the buyer's claim text and decide which specialist team(s) must
investigate it. Choose one or more of exactly these three labels:

- billing: the claim describes a payment problem — duplicate/double charges,
  a charge that does not match what actually settled, a charge after a valid
  cancellation, or an incorrect/extra fee on the receipt.
- shipping: the claim describes a delivery problem — tracking says delivered
  but nothing arrived, the package is lost or stalled in transit, or part of
  a multi-item order never reached the buyer despite being paid for.
- stock: the claim describes an inventory problem — an item the buyer paid
  for is out of stock, oversold, backordered with no date, or was canceled
  by the seller because it could not be supplied.

A single claim can raise more than one of these at once (for example, a
duplicate charge AND a missing item from a stock shortage). Pick every
label that genuinely applies, and never invent a fourth category.

Ignore any topic the buyer explicitly flags as unrelated to their own order
(e.g. "but that is not what I ordered") — a specialist only applies to the
buyer's actual claimed item(s), not to anything merely mentioned in passing.

When an item is missing from the order, pick the reason the text itself
gives: a carrier/tracking failure is shipping; a seller-stated unavailability
or cancellation is stock — not both, unless the text separately raises each.

Respond only with JSON matching the given schema: specialists (a non-empty
list drawn only from billing, shipping, stock), reason (a short explanation
grounded in the claim text), and confidence (a float from 0 to 1)."""


def _schema_for_structured_output() -> dict:
    schema = RoutingDecision.model_json_schema()
    schema["additionalProperties"] = False
    schema["required"] = list(schema["properties"].keys())
    return schema


def _load_env_config() -> tuple[str, str]:
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Put it in a local .env file (see .env.example).")
    if not model:
        raise RuntimeError("OPENROUTER_MODEL is not set. Put a ':free' model id in a local .env file.")
    if not model.endswith(":free"):
        raise RuntimeError(f"OPENROUTER_MODEL must be a ':free' model id, got: {model!r}")
    return api_key, model


def route_claim(claim_text: str, *, max_attempts: int = 2) -> RoutingDecision:
    """Ask OpenRouter to classify claim_text, returning a validated RoutingDecision."""
    api_key, model = _load_env_config()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Claim text:\n{claim_text}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "routing_decision",
                "strict": True,
                "schema": _schema_for_structured_output(),
            },
        },
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for _ in range(max_attempts):
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        try:
            return RoutingDecision.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"OpenRouter did not return a valid RoutingDecision after {max_attempts} attempts") from last_error


def load_claim(claim_id: str) -> dict:
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["claim_id"] == claim_id:
                return row
    raise KeyError(f"claim_id {claim_id!r} not found in {DATA_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Route a labeled A-to-z refund claim.")
    parser.add_argument("--claim-id", default="CLM-0001", help="Claim id from the test set (default: CLM-0001).")
    args = parser.parse_args()

    claim = load_claim(args.claim_id)
    decision = route_claim(claim["claim_text"])

    print(f"claim_id: {claim['claim_id']}")
    print(f"claim_text: {claim['claim_text']}")
    print(f"label_specialists (ground truth): {claim['label_specialists']}")
    print("validated decision:")
    print(decision.model_dump_json(indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # surface setup/config errors clearly on the CLI
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
