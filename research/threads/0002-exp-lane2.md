---
id: R-0002
title: Lane sonar to reduce unseen friendly lane collisions
status: open
owner: human
created: 2026-09-28
updated: 2026-09-28
confidence: historical-record-only
migrated_from:
  - INSIGHTS_AND_PLAYBOOK.md sections 4 and 6
---

# Lane sonar to reduce unseen friendly lane collisions

This is a migration of the in-progress `exp_lane2` note. It preserves what the playbook says without
asserting that the ignored experiment directory, raw output, or replays are still available.

## Evidence

The playbook records:

- V7.12 opening deaths at approximately 0.020 per dragon-turn versus approximately 0.012 for strong
  opponents during rounds 0–100.
- On Devil, `board_at.py` analysis attributed some `DOOMED` deaths to two friendly length-2 dragons
  entering the same one-tile lane from opposite ends while outside each other's 7×7 vision.
- The `exp_lane2` idea sends a dragon's head position and heading through its forward sonar ray, then
  treats a straight lane containing another seen or heard head as unsafe.
- A historical local result is recorded as 6/6 wins on Devil against V7.12, with 27–37 units at round
  100 instead of 10–15.

Provenance limitation: the tracked repository does not retain the commands, seeds, side allocation,
toolkit version, CPU peaks, raw output, replay IDs, or source snapshot for those numbers. `exp_*`
directories are gitignored. These claims are therefore `historical-record-only`.

## Interpretation

The recorded mechanism is plausible because local vision cannot reveal a friendly dragon approaching
from beyond the lane, while sonar can carry information along that lane. The Devil result suggests the
message may address a concrete coordination failure rather than merely changing movement preferences.
It does not establish generalization to other maps or ladder opponents.

## Hypothesis

Encoding head position and heading in forward sonar will reduce early friendly traffic traps and
`DOOMED` deaths in narrow lanes, increasing the surviving unit count without causing an offsetting
regression in CPU use, mining, combat, or other maps.

Discriminating measurements should include early deaths per dragon-turn by cause, units at round 100,
completed/error/timeout counts, CPU peak, and win totals on the full mandatory gate rather than Devil
alone.

## Proposed decision

The playbook's recorded next step is to run the mandatory local gate and, only if it passes, test against
strong ladder opponents. No implementation, battle, submission, or external test is authorized by this
migration.

## Adversarial review

No contemporaneous review was retained. Questions that remain open:

- Was 6/6 balanced across sides and multiple pearl seeds?
- Did sonar prevent collisions or merely alter traffic enough to change this sample?
- Does packing head position assume the map has already been identified?
- Can stale or delayed sonar make a safe lane look unsafe?
- Does repurposing the forward radar reduce enemy detection or conflict with later queen gossip?
- Does the benefit survive outside Devil and against non-V7.12 opponents?

## Human-approved decision

Not recorded. The existence of a playbook entry does not constitute approval to recreate, test, submit,
or activate this experiment.

## Implementation

The playbook names a scratch implementation `exp_lane2`, but no tracked implementation is linked from
this thread. Its current filesystem availability and exact source are not asserted.

## Experimental result

Historical-record-only: Devil versus V7.12, 6/6 wins, with 27–37 units at round 100 instead of 10–15.
The absence of raw artifacts prevents verification of configuration, comparability, and statistical
strength.

## Conclusion

Promising but unverified beyond the surviving note. The experiment remains open and has not passed the
documented promotion gate.

## Handoffs

Next human decision: either authorize recovery and inspection of any surviving scratch source, or
approve a fresh implementation from the documented hypothesis. If testing is authorized, the
implementation engineer must record exact provenance before handing results to an analyst and
adversarial reviewer.
