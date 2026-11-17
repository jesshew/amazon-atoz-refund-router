# Build Notes

## Status: code complete; live OpenRouter run left to the account owner

`router.py`, `schema.py`, env/gitignore setup, and dependency install are
done and verified locally (see checks below). The live OpenRouter call
needs a real `OPENROUTER_API_KEY` and a `:free` model id — those live only
in a local `.env` (`cp .env.example .env`, then fill it in) and were never
available in this environment, so the actual run was left for whoever holds
the key to do: `python router.py` prints the validated decision for
CLM-0001 (specialists, reason, confidence) straight to stdout.

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
- Did a row-by-row root-cause analysis of `label_specialists` across all 15
  claims (`ROUTING_ANALYSIS.md`). Finding: it's an alleged/topic-based
  routing label (what the buyer's text raises), not a verified-outcome label
  — CLM-0015 has all three specialists listed even though every allegation
  turns out false on investigation, since routing happens before
  investigation. That analysis surfaced two gaps in the original prompt,
  now fixed in `router.py`: (1) a disclaimed/unrelated mention (CLM-0010
  mentions "out of stock" but says "that is not what I ordered") must not
  add a specialist, and (2) shipping vs. stock for a missing item must
  follow the reason the text itself gives (carrier failure vs. seller-stated
  unavailability), not just the fact that something didn't arrive
  (CLM-0007).

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

Ignore any topic the buyer explicitly flags as unrelated to their own order
(e.g. "but that is not what I ordered") — a specialist only applies to the
buyer's actual claimed item(s), not to anything merely mentioned in passing.

When an item is missing from the order, pick the reason the text itself
gives: a carrier/tracking failure is shipping; a seller-stated unavailability
or cancellation is stock — not both, unless the text separately raises each.
```

## Left for the account owner to do

- [ ] Add a real `OPENROUTER_API_KEY` and a `:free` model id to a local `.env`
- [ ] Run `python router.py` and record the printed decision for claim 1
- [ ] Compare the returned `specialists` against `label_specialists` for CLM-0001 (`billing|shipping|stock`)
- [ ] Screenshot the OpenRouter Activity page showing the matching model id
