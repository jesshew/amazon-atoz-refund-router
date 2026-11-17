# Build Notes

## Status: complete — live run done

`router.py`, `schema.py`, env/gitignore setup, dependency install, and the
live OpenRouter call are all done and verified (see checks and printed
decision below).

**Model note:** the chosen `:free` model, `google/gemma-4-31b-it:free`, is a
real, currently-listed OpenRouter model (confirmed against the live
`/api/v1/models` catalog), but at run time it returned `429 Provider
returned error ... temporarily rate-limited upstream` on every attempt —
OpenRouter's shared free pool for that model was saturated, not a bug in
this code. To get the actual printed decision below, `.env` was pointed at
`nvidia/nemotron-3.5-lightning:free` instead, another currently-live `:free`
model, with no other change to `router.py`. Swapping back to
`google/gemma-4-31b-it:free` once the upstream limit clears requires only
editing `.env` — the code is model-agnostic.

## Printed decision for claim 1 (CLM-0001)

```
claim_id: CLM-0001
claim_text: I ordered a stroller and a car seat and my card was charged twice for the whole order. Only one box showed up with the stroller. Now the seller page says the car seat is out of stock. I want my money back for what I did not get and the extra charge.
label_specialists (ground truth): billing|shipping|stock
validated decision:
{
  "specialists": [
    "billing",
    "stock"
  ],
  "reason": "Buyer was charged twice for the order and the car seat is out of stock per the seller, so one paid item was not delivered and an extra charge occurred.",
  "confidence": 1.0
}
```

**How this compares to `label_specialists`:** ground truth is
`billing|shipping|stock`; the model returned `billing|stock` — it correctly
caught the double charge (billing) and the seller's out-of-stock statement
(stock), but missed `shipping`. Per `ROUTING_ANALYSIS.md`, CLM-0001's
`shipping` label comes from the SYSTEM_PROMPT's own shipping criterion
("part of a multi-item order never reached the buyer despite being paid
for") — the car seat is a separate line that never arrived, independent of
why. The model collapsed that into the stock explanation instead of also
flagging it as a shipping-level fulfillment gap. This is a real, expected
limitation of a small free-tier model on one sample, not a schema or
pipeline failure — the output is still a valid, schema-conformant
`RoutingDecision` with reasonable (if partial) reasoning.

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

- [ ] Screenshot the OpenRouter Activity page for this run, showing model id
      `nvidia/nemotron-3.5-lightning:free` (that page is tied to the account
      that owns the key, so it has to come from the key holder's own browser
      session, not from this environment)
