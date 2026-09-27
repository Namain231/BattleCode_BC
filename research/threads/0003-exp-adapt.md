---
id: R-0003
title: Adapt queen timing to a large enemy dragon
status: open
owner: human
created: 2026-09-28
updated: 2026-09-28
confidence: historical-record-only
migrated_from:
  - INSIGHTS_AND_PLAYBOOK.md sections 2, 4, and 6
---

# Adapt queen timing to a large enemy dragon

This is a migration of the in-progress `exp_adapt` note. It records the surviving motivation,
hypothesis, and result without reconstructing missing experimental details.

## Evidence

The playbook records:

- Against `!ghaplebaaz` on Trauma, an opponent grew one dragon from early in the game and finished with
  a length advantage despite V7.12 having greater total length.
- The recorded example says V7.12 lost with 82 total length versus 25 because its queen started only
  around round 340 and reached length 18.
- The proposed `exp_adapt` mechanism gossips the longest observed enemy. After round 300 on a maze map,
  if that enemy is at least length 10 and at least three longer than our queen, our queen forms and
  feeding begins early.
- The playbook describes the experiment as neutral in self-play and needing a ladder test against a
  giant-growing opponent.

Provenance limitation: no battle/game IDs, replay reference, commands, seeds, map panel, raw self-play
totals, toolkit version, CPU results, or tracked experiment source accompany these claims. They are
`historical-record-only`.

## Interpretation

V7.12's fixed late-queen timing may react too slowly when the opponent is already building the
round-500 longest dragon. Enemy-length gossip could provide a trigger for earlier consolidation.
Neutral self-play neither validates nor refutes the mechanism because both sides may share the same
macro and the intended target is an asymmetric giant-growing strategy.

## Hypothesis

When a maze-map opponent establishes a clearly larger dragon after round 300, communicating that length
and starting queen protection and feeding early will improve longest-dragon outcomes without
unnecessarily collapsing the swarm in games where no giant threat exists.

A discriminating experiment requires an opponent known to grow a giant and should measure trigger
frequency, queen length over time, living units, total length, longest length, feeding deaths, CPU peak,
and final result. General gate performance remains necessary to detect overreaction regressions.

## Proposed decision

The surviving proposal is to test against a giant-growing ladder opponent after local sanity checks.
This migration does not authorize implementation, submission, activation, or a challenge.

## Adversarial review

No contemporaneous review was retained. Questions that remain open:

- How reliable is the maximum enemy length when observations and sonar gossip are stale?
- Could one transient or doomed enemy trigger a costly irreversible feed?
- Is a three-segment lead enough to justify abandoning swarm strength?
- Does the trigger duplicate or conflict with V7.12's existing queen gossip?
- Should response depend on rounds remaining, map topology, our total length, or opponent total length?
- Can the test separate adaptation value from random pearl timing?

## Human-approved decision

Not recorded. The playbook note is not approval for further action.

## Implementation

The playbook names a scratch implementation `exp_adapt`, but no tracked source snapshot is linked from
this thread. Its current filesystem availability and exact implementation are not asserted.

## Experimental result

Historical-record-only: neutral in unspecified self-play. No totals or raw artifacts are retained in
the tracked repository, so the result is inconclusive and cannot support promotion.

## Conclusion

The hypothesis remains open. Existing evidence identifies a relevant failure mode, but the adaptation
has not been validated against the strategy it is meant to counter.

## Handoffs

Next human decision: approve or reject recovery/reimplementation and define an acceptable giant-growing
opponent test. Any future handoff must include exact source provenance and distinguish local evidence
from ladder evidence.
