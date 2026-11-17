# Build Notes

## Status: scaffolding complete, pending a real OpenRouter key

`router.py`, `schema.py`, env/gitignore setup, and dependency install are
done and verified locally (see checks below). The live OpenRouter call and
the printed decision for claim 1 are **pending** — that needs a real
`OPENROUTER_API_KEY` and a `:free` model id in a local `.env`
(`cp .env.example .env`, then fill it in). Once that's in place, running
`python router.py` will print the validated decision for CLM-0001, and
this file will be updated with that output plus the comparison against
`label_specialists`.

## What was checked so far

- `pip install -r requirements.txt` succeeds in a clean venv.
- Running `router.py` with no `.env` fails with a clear
  `OPENROUTER_API_KEY is not set` error (exit code 1) instead of a stack
  trace — config errors are surfaced, not silently swallowed.
- `RoutingDecision` (in `schema.py`) correctly **rejects** an out-of-vocabulary
  specialist (e.g. `"refund"`) and a confidence outside `[0, 1]`, confirmed
  with direct Pydantic validation calls.
- Inspected all 15 rows of `data/Labeled Amazon A-to-z Refund Claims
  (15-claim test set).csv`: `label_specialists` contains multi-value entries
  like `billing|shipping|stock`, which is why `RoutingDecision.specialists`
  is a non-empty list rather than a single enum value.

## Key system-prompt excerpt (router.py)

```
- billing: the claim describes a payment problem — duplicate/double charges,
  a charge that does not match what actually settled, a charge after a valid
  cancellation, or an incorrect/extra fee on the receipt.
- shipping: the claim describes a delivery problem — tracking says delivered
  but nothing arrived, the package is lost or stalled in transit, or part of
  a multi-item order never reached the buyer despite being paid for.
- stock: the claim describes an inventory problem — an item the buyer paid
  for is out of stock, oversold, backordered with no date, or was canceled
  by the seller because it could not be supplied.

A single claim can raise more than one of these at once...
```

## Pending (fill in once a key is available)

- [ ] Printed decision for claim 1 (`python router.py`)
- [ ] How the returned `specialists` compares to `label_specialists` for CLM-0001 (`billing|shipping|stock`)
- [ ] OpenRouter Activity page screenshot showing the matching model id
