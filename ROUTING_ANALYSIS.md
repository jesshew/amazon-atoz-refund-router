# Root-Cause Analysis: `label_specialists` Across the 15-Claim Test Set

Scope: only `label_specialists` (billing / shipping / stock, pipe-separated).
`label_resolution`, `label_refund_amount`, `label_has_conflict` are treated
as downstream/orthogonal outputs, used here only as evidence for *why* a
specialist was or wasn't assigned.

## Decision Rules

**billing** — triggered when the claim text alleges a payment/charge problem
tied to the buyer's own order: duplicate/double charges, a charge count that
doesn't match what the buyer expects, a charge that posted after a valid
cancellation, or an extra/incorrect fee on the receipt.
- Evidence: CLM-0002 — "I can see two charges for the same knife set... my
  available balance dropped twice."
- Evidence: CLM-0009 — "the full payment posted to my card two days later. I
  have not received a credit."

**shipping** — triggered when the claim text alleges a delivery/fulfillment
failure where the *stated reason* is a carrier/tracking/fulfillment problem
(not seller-declared unavailability): non-delivery, tracking stalled, a
delivery scan contradicted by the buyer's own observation, or an item
missing from a shipped order with no unavailability reason given.
- Evidence: CLM-0003 — "the tracking has not moved beyond the carrier
  depot... nothing ever reached me."
- Evidence: CLM-0010 — "The set arrived without its spatula" (no
  unavailability reason stated → defaults to shipping, not stock).

**stock** — triggered specifically when the text attributes a missing or
unfulfilled item to seller-declared *unavailability*: "out of stock," "no
longer available," "canceled," "sold out," "cannot give a date."
- Evidence: CLM-0004 — "the seller now says there are none left and cannot
  give me a date."
- Evidence: CLM-0007 — "an email saying the shade is no longer available."

**Core disambiguator (shipping vs. stock for a missing item):** the label
follows the *reason the text gives* for the absence, not the mere fact that
something didn't arrive. Carrier/tracking failure → shipping. Seller-stated
unavailability/cancellation → stock. The same surface complaint ("I didn't
get X") routes differently depending on this one textual cue.

## Main Scenarios

1. **Single-topic** — only one problem type appears in the text.
   CLM-0003, CLM-0010 (shipping only); CLM-0004, CLM-0011 (stock only);
   CLM-0002, CLM-0009 (billing only).
2. **Billing + shipping** — a payment discrepancy alongside a non-delivery
   with no unavailability reason. CLM-0005, CLM-0012.
3. **Billing + stock** — charged for a line the seller canceled/couldn't
   supply. CLM-0007, CLM-0014.
4. **Shipping + stock** — a missing item where delivery records and
   inventory/pick records disagree. CLM-0006, CLM-0013 (both also
   `has_conflict=true`).
5. **All three** — a payment discrepancy plus a delivery problem plus an
   availability problem, all independently stated. CLM-0001, CLM-0008,
   CLM-0015.

## Edge Cases

**CLM-0002** — naive guess: `billing` only is actually right, but a
keyword/heuristic classifier might second-guess itself once it learns the
investigation found only one real charge (`no_refund`, $0) and drop billing
entirely. Actual: `billing`. Why: the whole complaint is a payment-discrepancy
allegation ("two charges... balance dropped twice"); nothing in the text
touches delivery or availability. `label_specialists` tracks the alleged
topic, not whether the investigation sustained it — the pending-authorization
finding affects `label_resolution`, not `label_specialists`.

**CLM-0010** — naive guess: `shipping|stock`, because the word "out of
stock" appears in the text. Actual: `shipping` only. Why: the buyer
explicitly disclaims that mention — "that is not what I ordered" — and
`label_notes` confirms it's "unrelated." Rule: a topic only counts if it
pertains to the buyer's *own* claimed item; keyword presence alone
over-triggers.

**CLM-0007** — naive guess: `billing|shipping`, since an item missing from a
delivered package reads like a fulfillment/shipping issue. Actual:
`billing|stock`. Why: the text supplies the reason itself — "no longer
available" — which is the stock signal, not a carrier/tracking signal. This
is the central shipping-vs-stock disambiguation case.

**CLM-0012** — naive guess: `shipping` only, since the buyer hedges the
second charge ("what looks like another charge") and `label_notes` later
shows it never settled. Actual: `billing|shipping`. Why: the buyer
independently raised a payment concern in their own words, so billing is
routed for investigation regardless of the eventual finding that it was a
non-settling pending authorization. Confirms the alleged-vs-verified
distinction.

**CLM-0015** — naive guess (for a model trying to anticipate the outcome
rather than just classify the complaint): suppress some/all specialists
since the investigation found every allegation baseless (`no_refund`, $0).
Actual: `billing|shipping|stock`. Why: all three complaints are
independently and explicitly stated in the text (duplicate charge, tracking
said not delivered, seller said out of stock), even though every one of them
turns out false. This is the strongest single piece of evidence that
`label_specialists` is a **routing/triage** label — which team(s) must check
the claim — fully decoupled from whether the claim is ultimately valid.

**CLM-0006, CLM-0008, CLM-0013 (`label_has_conflict=true`)** — naive guess:
a "conflict" status itself adds or changes which specialists are listed.
Actual: specialists follow the same topic-presence rule as every other row;
`has_conflict` is a separate signal meaning two authoritative records (e.g.
carrier delivery scan vs. warehouse/pick records, or completed payments vs.
a non-delivered item) directly contradict each other and need investigator
judgment. It doesn't correlate with specialist count: CLM-0006/CLM-0013 are
2-specialist claims *with* conflict, while CLM-0005 is also a 2-specialist
claim *without* conflict. Orthogonal axes.

## Verdict: Alleged vs. Verified

`label_specialists` is assigned from what the buyer's claim text **alleges**
— which problem topics it raises about the buyer's own order — not from
what the investigation ultimately **verifies**. CLM-0002, CLM-0012, and
especially CLM-0015 each contain at least one specialist label for a
complaint that `label_notes`/`label_resolution` later show to be false or
unsettled. Routing happens before investigation; it has to be alleged-based
by construction, since a router can't know the verified facts in advance.

The one real constraint on "alleged" is CLM-0010: a topic has to belong to
the buyer's *own* complaint, not just appear anywhere in the narrative.

## Recommendation for `router.py`'s `SYSTEM_PROMPT`

The current prompt (`router.py` lines 25–45) already frames each label as
"the claim describes a problem" — alleged/topic-based framing, which is the
right premise. Two gaps, both concrete and worth adding:

1. No rule for CLM-0010-style disclaimed mentions. Add, after the three
   bullet definitions (after line 37):
   > Ignore any topic the buyer explicitly flags as unrelated to their own
   > order (e.g. "but that is not what I ordered") — a specialist only
   > applies to the buyer's actual claimed item(s).

2. The shipping/stock bullets (lines 32–37) don't state the disambiguator
   explicitly — a model could plausibly tag a missing-shade complaint as
   shipping (item never arrived) instead of stock (seller said unavailable).
   Add, right after line 37:
   > When an item is missing from the order, pick the reason the text
   > itself gives: a carrier/tracking failure is shipping; a seller-stated
   > unavailability or cancellation is stock — not both, unless the text
   > separately raises each.

No change needed to the "classify by what's described in the text" premise
itself — it's already correct per CLM-0002/0012/0015.
