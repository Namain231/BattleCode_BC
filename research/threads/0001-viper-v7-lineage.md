---
id: R-0001
title: Viper V7.5 to V7.12 lineage and current champion
status: promoted
owner: human
created: 2026-09-28
updated: 2026-09-28
confidence: measured-ladder-noisy
migrated_from:
  - AGENTS.md
  - INSIGHTS_AND_PLAYBOOK.md sections 3 and 5
---

# Viper V7.5 to V7.12 lineage and current champion

This record preserves the lineage currently summarized in `AGENTS.md` and
`INSIGHTS_AND_PLAYBOOK.md`. Those files remain authoritative for the current champion and current
strategy. This thread records the surviving historical claims and their limitations.

## Evidence

- The repository retains source snapshots in `baselines/v7_5`, `baselines/v7_9`,
  `baselines/v7_10`, `baselines/v7_11`, and `baselines/v7_12`.
- `AGENTS.md` designates V7.12 in `baselines/v7_12` as the current champion and records submission
  8242 as active at the time of that note.
- `AGENTS.md` and `INSIGHTS_AND_PLAYBOOK.md` record this strategy lineage:
  - V7.5: miners.
  - V7.9: short-horizon early miners.
  - V7.10: even head-on trades.
  - V7.11: continued budding on Autarky.
  - V7.12: late queen formation and feeding on maze maps.
- The same notes record maze-panel totals of V7.5 14/28, V7.10 approximately 19/28, and V7.12
  23/28 against 777, ANON_TOKYO, hmm, and Aviators.
- `AGENTS.md` contains the map-by-map V7.5 and V7.12 panel summaries that survived into the current
  repository.

Provenance limitation: no battle IDs, game IDs, replay manifest, exact run dates, or raw panel output
are retained with these totals. They are therefore historical repository records, not independently
reproduced evidence in this migration. Opponent bots may also have changed between panels.

## Interpretation

The retained history attributes each promoted version to a focused strategic change and says each step
was kept only after passing the ladder panel. The available records support the current lineage summary,
but they are insufficient for a same-session statistical comparison between every version.

## Hypothesis

The original version-by-version hypotheses were not retained in a structured form. Inferring more than
the short strategy labels above would fabricate history.

## Proposed decision

Historical proposals for V7.5 through V7.12 were not retained. The surviving repository state indicates
that V7.12 was proposed as the champion after its late-queen changes.

## Adversarial review

No contemporaneous adversarial review was retained. Current caveats are:

- self-play is not a reliable ladder predictor;
- one game per map is noisy;
- panels run at different times may face different opponent code;
- the approximately 19/28 V7.10 total is explicitly approximate; and
- missing battle IDs and raw output prevent independent reconstruction.

## Human-approved decision

The repository records the human team decision to retain V7.12 as champion and submission 8242 as
active. The approver identity, approval timestamp, and candidate commit were not recorded and must not
be invented.

## Implementation

The retained implementations are the corresponding `baselines/v7_*` directories. The editable working
copy is `viper_v7/`. This migration does not modify or revalidate any bot source.

## Experimental result

Historical-record-only results:

- V7.5 maze panel: 14/28.
- V7.10 maze panel: approximately 19/28.
- V7.12 maze panel: 23/28.

The detailed V7.12 record in `AGENTS.md` is 777 4/7, ANON_TOKYO 7/7, hmm 6/7, and Aviators
6/7. No raw replay references are available in the tracked repository.

## Conclusion

V7.12 remains the documented champion. This conclusion reflects the current human-maintained project
state, not a newly run experiment. A future champion must follow the existing mandatory promotion gate.

## Handoffs

No active handoff. If V7.12 is superseded, preserve this conclusion, append a `supersede` event to
`research/log.jsonl`, link the new thread, and update `AGENTS.md` plus `INSIGHTS_AND_PLAYBOOK.md` in the
same commit.
