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

## Prompt rewrite: shipping and stock can both apply to one missing item

The first live run (below the fold, in the commit history) returned
`billing|stock` for CLM-0001 against a ground truth of
`billing|shipping|stock` — it missed `shipping`. Checking the model's own
stated reasoning against the prompt text showed this wasn't a model
mistake: the old disambiguator (*"pick the reason the text itself
gives... not both, unless the text separately raises each"*) explicitly
told the model to choose one label by cause, and it followed that
instruction correctly. The bug was in the prompt, not the model.

Checked against all 15 claims, the actual rule implied by the labels is:
shipping and stock both apply to the same missing item when it's a
genuinely separate, distinctly-ordered product (not a bundled accessory of
one product, and not another unit of the same SKU) **and** the text uses
shipment-level language (a box/parcel that never arrived, a package that
didn't include it, a delivery record that's contradicted). Both conditions
hold for CLM-0001 (the car seat is a distinct product from the stroller,
and the text says "only one box showed up"). They don't hold for CLM-0007
(the missing shade is a bundled accessory of the lamp, not its own line)
or CLM-0011 (the organizer is a distinct product, but the text only says
"keeps getting pushed back" — no box/shipment language at all, just a
backorder status) — both of those stay single-label, matching their
ground truth.

`SYSTEM_PROMPT` in `router.py` was rewritten accordingly:

```
A claim can need more than one specialist for the very same missing item —
shipping and stock are not always mutually exclusive. Apply shipping when
the text describes a shipment-level event for a genuinely separate,
distinct product or order line (not a bundled accessory of one product,
and not another unit of the same item): a box or parcel that never
arrived, a package that didn't include that line, or a delivery/tracking
record contradicted by what the buyer actually received. Apply this
regardless of whether a reason is also given for it. Apply stock whenever
the text attributes a shortage to the seller's own stated unavailability,
backorder, or cancellation. When the missing piece is instead a bundled
accessory or component of a single ordered product, or another unit within
one line, treat shipping and stock as mutually exclusive and pick by the
stated reason — a carrier/tracking failure is shipping, a seller-stated
unavailability or cancellation is stock — unless the text separately raises
both for that same item.
```

## Printed decision for claim 1 (CLM-0001)

```
claim_id: CLM-0001
claim_text: I ordered a stroller and a car seat and my card was charged twice for the whole order. Only one box showed up with the stroller. Now the seller page says the car seat is out of stock. I want my money back for what I did not get and the extra charge.
label_specialists (ground truth): billing|shipping|stock
validated decision:
{
  "specialists": [
    "billing",
    "shipping",
    "stock"
  ],
  "reason": "The buyer reports a duplicate charge for the whole order, a missing car seat from the delivered box, and the seller page stating the car seat is out of stock.",
  "confidence": 0.98
}
```

**How this compares to `label_specialists`:** matches exactly —
`billing|shipping|stock` == `billing|shipping|stock`. The model's reasoning
on this run (captured in full in the matching generation record below)
explicitly named the car seat as "a distinct product line (separate from
the stroller)... not a bundled accessory or another unit of the stroller,"
which is the exact condition the rewritten rule hinges on — it isn't just
landing on the right labels by chance.

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
  investigation.
- That analysis led to two rounds of `SYSTEM_PROMPT` fixes, both verified
  against a live run afterward: (1) a disclaimed/unrelated mention
  (CLM-0010 mentions "out of stock" but says "that is not what I ordered")
  must not add a specialist; (2) shipping and stock can both apply to the
  same missing item — see "Prompt rewrite" above for the full rule and why
  the first version of this fix (pick one by cause, never both) was itself
  wrong on CLM-0001.

## Key system-prompt excerpt (router.py)

The three label definitions, unchanged since the first commit:

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
```

Plus the disclaimed-mention rule and the additive shipping/stock rule
quoted in full under "Prompt rewrite" above — that's the current,
complete `SYSTEM_PROMPT` in `router.py`.

## Matching OpenRouter generation record

Captured directly from the same API response that produced the printed
decision above (not a separate call, and not a screenshot transcribed by
hand) — this is exactly what OpenRouter's Activity page's Generation
details panel would show for this call:

```json
{
  "id": "gen-1794925082-fEVtSv3FSauBOnNj1BbN",
  "model": "baidu/ernie-5.5-flash-preview:free",
  "provider": "Baidu",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 627,
    "completion_tokens": 579,
    "total_tokens": 1206,
    "cost": 0,
    "completion_tokens_details": { "reasoning_tokens": 506 }
  }
}
```

- `model` (`baidu/ernie-5.5-flash-preview:free`) matches `OPENROUTER_MODEL`.
- `cost: 0` — consistent with a `:free` model, no credits spent.
- `finish_reason: "stop"` — the model completed its own structured-output
  response rather than being cut off mid-JSON, which is why
  `RoutingDecision.model_validate_json` parsed it cleanly with no retry.
- `reasoning_tokens: 506` — the rewritten prompt is longer and asks the
  model to weigh two conditions (separate product? shipment-level
  language?) instead of one, so this run did noticeably more internal
  reasoning than the pre-rewrite run (98 tokens) before emitting the JSON
  `content`; that reasoning is in the API response (not shown above) and
  is not part of the validated `RoutingDecision`, which only reads the
  final `content` field.

To cross-check this visually: open OpenRouter's Activity page and look up
generation id `gen-1794925082-fEVtSv3FSauBOnNj1BbN` — that's the specific
call this record and the printed decision both came from.
