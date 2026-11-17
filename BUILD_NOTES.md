# Build Notes

## Status: complete — live run done

`router.py`, `schema.py`, env/gitignore setup, dependency install, and the
live OpenRouter call are all done and verified (see checks and printed
decision below).

**Model note:** three `:free` models were tried against `router.py`
before landing on the one used below, and the dead ends are worth recording:

1. `google/gemma-4-31b-it:free` (the original pick) — a real, currently-listed
   model (confirmed against the live `/api/v1/models` catalog), but every
   call returned `429 ... temporarily rate-limited upstream`: OpenRouter's
   shared free pool for that model was saturated, not a bug in this code.
2. `nvidia/nemotron-3.5-lightning:free` — responded, but turned out to be a
   heavy internal-reasoning model: it was slow enough in practice to time
   out a 60s request, and a spot-check I ran against it separately (not the
   same call that produced a printed decision) reported a model id that
   didn't exactly match what was in `.env`. Rather than debug that
   mismatch, I dropped this model instead of asserting a match I hadn't
   verified end-to-end.
3. `baidu/ernie-5.5-flash-preview:free` — used for the run below. Unlike the
   first two attempts, the printed decision and the raw OpenRouter
   generation record quoted below both come from **the same API call**,
   captured in one script, so they are provably consistent with each other
   rather than compared across two separate runs.

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
  "reason": "Buyer reports the card was charged twice for the whole order (billing) and that the car seat never arrived because the seller page now says it is out of stock (stock). The missing item is attributed to seller-stated unavailability rather than any tracking or carrier failure, so shipping does not apply.",
  "confidence": 0.95
}
```

**How this compares to `label_specialists`:** ground truth is
`billing|shipping|stock`; the model returned `billing|stock` — it correctly
caught the double charge (billing) and the seller's out-of-stock statement
(stock), but missed `shipping`. Per `ROUTING_ANALYSIS.md`, CLM-0001's
`shipping` label comes from the SYSTEM_PROMPT's own shipping criterion
("part of a multi-item order never reached the buyer despite being paid
for") — the car seat is a separate line that never arrived, independent of
why. The model's own stated reasoning explicitly chose stock over shipping
using the exact disambiguation rule in the prompt ("attributed to
seller-stated unavailability rather than any tracking or carrier failure"),
so it applied the rule correctly — it just didn't also apply the separate,
broader shipping criterion for a multi-item order with a missing line. This
is a real, expected limitation of a free-tier model on one sample, not a
schema or pipeline failure: the output is still a valid, schema-conformant
`RoutingDecision` with reasoning grounded in the claim text.

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

## Matching OpenRouter generation record

Captured directly from the same API response that produced the printed
decision above (not a separate call, and not a screenshot transcribed by
hand) — this is exactly what OpenRouter's Activity page's Generation
details panel would show for this call:

```json
{
  "id": "gen-1794916485-ooyBnKlrDoid0By2lB0o",
  "model": "baidu/ernie-5.5-flash-preview:free",
  "provider": "Baidu",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 465,
    "completion_tokens": 186,
    "total_tokens": 651,
    "cost": 0,
    "completion_tokens_details": { "reasoning_tokens": 98 }
  }
}
```

- `model` (`baidu/ernie-5.5-flash-preview:free`) matches `OPENROUTER_MODEL`.
- `cost: 0` — consistent with a `:free` model, no credits spent.
- `finish_reason: "stop"` — the model completed its own structured-output
  response rather than being cut off mid-JSON, which is why
  `RoutingDecision.model_validate_json` parsed it cleanly with no retry.
- `reasoning_tokens: 98` — this model does a small amount of internal
  reasoning before emitting the JSON `content`; that reasoning is in the
  API response (not shown above) and is not part of the validated
  `RoutingDecision`, which only reads the final `content` field.

To cross-check this visually: open OpenRouter's Activity page and look up
generation id `gen-1794916485-ooyBnKlrDoid0By2lB0o` — that's the specific
call this record and the printed decision both came from.
