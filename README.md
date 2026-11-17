# A-to-z Refund Claim Router

Classifies Amazon A-to-z Guarantee refund claims into one or more specialist
teams (`billing`, `shipping`, `stock`) using an OpenRouter model with
structured output, validated against a Pydantic schema.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your real key and model id
```

`.env` holds two values, both read from the environment (never hardcoded):

- `OPENROUTER_API_KEY` — from https://openrouter.ai/keys (free account)
- `OPENROUTER_MODEL` — any OpenRouter model id ending in `:free`

## Run

```bash
python router.py                      # routes claim CLM-0001
python router.py --claim-id CLM-0007   # routes any claim from the test set
```

## Files

- `schema.py` — `RoutingDecision`: `specialists` (list of `billing`/`shipping`/`stock`,
  no duplicates, non-empty), `reason` (str), `confidence` (float 0–1).
- `router.py` — builds the JSON schema from `RoutingDecision`, calls OpenRouter's
  structured-output endpoint, and validates the reply with Pydantic before printing it.
- `data/` — the labeled 15-claim test set.
- `BUILD_NOTES.md` — the printed decision for claim 1, how it compares to the
  ground-truth label, and what was checked.
