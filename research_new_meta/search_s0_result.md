# search_s0: offline addressable-loss audit
Date: 2026-10-02. Verdict: **NO-GO under the S0 gate.**

## Decision
The plan requires at least approximately 15% of our mean lost length to be visible-and-avoidable, **and** our share to be clearly above top-team winners. The strict preceding-round proxy is **9.50% for our ladder games**, **10.44% for our losses**, and **16.79% for retained local vB19 sides versus 16.74% for top winners**. Neither our ladder corpus nor the local cohort clears both conditions. Do not start S1/S2 on the strength of this audit.

This is the plan's visibility-plus-single-step-alternative proxy, not demonstrated survival under a three-round rollout. It does not establish that exactly these losses could actually have been saved, or that other losses could not benefit from search.

## Inputs and scope
Read search_layer_plan.md (especially section 2e), AGENT_LOG.md, the insights.md rule-change banner, README.md, guide/, and local rule documentation. research_new_meta/loong_blog/DIGEST.md was absent; inspected the available engine/planning posts directly. Their reference-engine claims may change the feasibility assumptions of the old plan, but do not supply evidence of S0 tactical value. The blog itself marks earlier strategy/training as predating the new rules.

No bot edits, API calls, games, replay generation, .pkl caches, or analysis-script files. Python 3.11 was invoked through cached uv with PYTHONDONTWRITEBYTECODE=1. The code ran inline, using tools/replay_lite.py and rulemine/mapgeo.py, following rulemine/state.py's event reconstruction.

The requested out/sw_2 replays had already been deleted (only summary.json remained). Existing scout_v6/manifest.csv lists 324 games: 306 top-team wins and 18 own wins. We audited every available game involving team 98, including eight losses stored under the top winner's directory.

| Cohort | Selected side observations | Physical replay inputs / selection |
|---|---:|---|
| Our ladder games | 26 (18 wins, 8 losses) | All manifest games where teamA or teamB is 98; all 10 live maps |
| Top winners | 67 | All 12 top teams; deterministic 5/team sample plus the union of games involving us |
| Local vB19 | 48 | 40 f1_h2h replay sides plus both sides of 4 unique f1b_control self-play replays |
| Total | 167 | **129 physical replays = 85 public + 44 local** |

Public overlap is eight games counted once for our losing side and once for the top winning side: 67 + 26 - 8 = 85. Local control files were SHA256-deduplicated; their two sides remain correlated observations. Inputs were frozen during processing, so subsequent concurrent panel output was not added.

Top sampling: group manifest top rows by winner_team; for each team in manifest order, shuffle its game keys using random.Random(20261002 + int(team)), retain the first five, and union these with all games involving team 98. Paths are ladder/scout_v6/{group}/{winner_team}/{game}.replay. Local inputs came from sorted out/f1_h2h/*.replay and out/f1b_control/*.replay, deduplicated by physical bytes; select sides whose replay bot path identifies /vB19-. These are retained controls, not a rerun of the missing sweep. Public bot provenance varies; our ladder cohort is team 98's recorded submissions, not necessarily today's vB19.

## Method
1. Decode only roundStart, turnStart, dragonAction, dragonUpdate, dragonSplit and dragonDeath. Initialize exact bodies and topology from replay map text. Maintain living IDs, team, bodies, and occupancy incrementally.
2. At each selected victim's turnStart, retain its latest four snapshots: round, IDs of other heads within wrapped Chebyshev radius 3, and legal cardinal directions. A legal first step crosses no kelp, lands on no body/head (own tail included), and lands within the victim's current 7x7. Portal exits outside that view are excluded. Record the actual first direction when dragonAction arrives.
3. Apply each dragonUpdate by inserting the reported new head and popping tails until the reported tail matches. Sprint updates are per successful step; no intermediate-cell interpolation is required. Apply split bodies exactly; splits redistribute length and are not losses.
4. Count **every dragonDeath**, including passive head-on victims killed during another dragon's turn. Attribute an active collision to the occupant at its fatal next destination. For head-on pairs, attribute the passive victim to the active mover and retain the passive victim ID for the mover's subsequent death. Body collision's killer is the body owner's ID; its head need not be visible.
5. Length at death is the body's length after any completed sprint steps, before removing the dead dragon. Total lost length is death length plus positive net length shrink on successful movement updates. This is net material shrink, not gross paid sprint costs: a paid step offset by eating is not a net loss. Explicit suicide remains in the denominator and is excluded from the avoidable numerator.
6. **Strict primary timing:** t is the death's replay round. Examine victim decision snapshots at exactly t-1, t-2 and t-3. At each, the eventually colliding dragon's head must have been visible, and at least one legal direction must differ from the recorded first move. For split/suicide actions there is no recorded first direction, so a legal move is an alternative action. Visibility and alternative must occur in the **same snapshot**. Missing pre-birth snapshots contribute no hint.
7. Count each death's length once in the cumulative union over the three preceding rounds, even if several qualify. Wall, self and no-valid-action deaths have no other killer head; they stay in the denominator but cannot enter this particular killer-head numerator. Report them separately.
8. Secondary timing uses the latest three victim decision snapshots, which can include the fatal turn for an active victim. It is labeled separately and does not replace the strict prior-round gate.

Reproduction core, for each death i at round t:
```python
L = len(bodies[i])                         # after completed steps
prior = [s for s in history4[i] if 1 <= t - s["round"] <= 3]
eligible = any(
    killer is not None and killer in s["visible_heads"]
    and bool(s["legal_dirs"] - ({s["recorded_first"]} if s["recorded_first"] is not None else set()))
    for s in prior
)
lost_length += L
if eligible and not explicit_suicide:
    visible_and_alternative_length += L
    visible_and_alternative_deaths += 1
# Separately add max(0, old_length - updated_length) for successful moves;
# never add split-parent shrink, and count both head-on death events.
```

## Primary results
Length-weighted share = sum qualifying death length / sum total lost length, equivalently mean qualifying length per game / mean lost length per game.

| Cohort | All deaths | Death length | Movement net shrink | Total lost length | Prior-3 qualifying length | Share | Qualifying dragons / all deaths |
|---|---:|---:|---:|---:|---:|---:|---:|
| Our ladder games | 5,646 | 16,205 | 810 | 17,015 | 1,616 | **9.50%** | 513 / 5,646 = 9.09% |
| Our eight losses | 1,981 | 5,958 | 179 | 6,137 | 641 | **10.44%** | 213 / 1,981 = 10.75% |
| Our 18 wins | 3,665 | 10,247 | 631 | 10,878 | 975 | **8.96%** | 300 / 3,665 = 8.19% |
| Local vB19 | 10,158 | 29,966 | 2,640 | 32,606 | 5,475 | **16.79%** | 1,792 / 10,158 = 17.64% |
| Top winners | 17,941 | 48,630 | 475 | 49,105 | 8,218 | **16.74%** | 2,846 / 17,941 = 15.86% |

| Cohort | Mean total lost length | Mean prior-3 qualifying length |
|---|---:|---:|
| Our ladder games | 654.42 | 62.15 |
| Our losses | 767.13 | 80.13 |
| Local vB19 | 679.29 | 114.06 |
| Top winners | 732.91 | 122.66 |

### Preceding-round visibility and alternatives
Each entry is cumulative length: t-1 alone / union of t-1..t-2 / union of t-1..t-3. These are unions, not three independent categories.

| Cohort | Killer head visible | Visible plus distinct legal alternative | Qualifying death count |
|---|---|---|---|
| Our ladder games | 1,595 / 1,734 / 1,846 | 1,275 / 1,462 / 1,616 | 428 / 474 / 513 |
| Our losses | 657 / 695 / 749 | 507 / 579 / 641 | 175 / 196 / 213 |
| Local vB19 | 5,628 / 5,923 / 6,371 | 4,391 / 5,028 / 5,475 | 1,504 / 1,693 / 1,792 |
| Top winners | 9,354 / 9,531 / 9,643 | 6,455 / 7,694 / 8,218 | 2,220 / 2,673 / 2,846 |

The eventual killer's head was never visible in these preceding rounds for **60.25% of our collision-lost length** (2,798/4,644), 57.18% in our losses (1,000/1,749), 50.76% locally (6,568/12,939), and 36.97% for top winners (5,655/15,298). This is a share of collision losses, not all losses; visible body-only obstacles can still be useful.

### Every death reason
Entries are dragons / length lost, including intentional deaths when their intent cannot be established.

| Reason | Our ladder games | Our losses | Local vB19 | Top winners |
|---|---:|---:|---:|---:|
| Wall | 1,898 / 5,260 | 632 / 1,885 | 6,039 / 16,555 | 6,487 / 15,214 |
| Self | 1,961 / 5,455 | 639 / 1,949 | 117 / 329 | 5,467 / 15,986 |
| Other body | 235 / 865 | 95 / 321 | 515 / 2,216 | 1,966 / 5,133 |
| Head-on | 1,251 / 3,779 | 478 / 1,428 | 3,432 / 10,723 | 3,389 / 10,165 |
| No valid action | 301 / 846 | 137 / 375 | 55 / 143 | 632 / 2,132 |

Passive head-on victims counted: ours 516, losses 226, local 1,713, top 1,575. Missing victim decision history: 13, 6, 54 and 35 deaths respectively. These are counted in losses, not silently dropped.

## Sensitivities and uncertainty
- **Latest three decisions, potentially including the fatal turn:** ours 11.53%, losses 13.35%, local 20.15%, top 18.55%. Our ladder cohort still fails the 15% bar. Within that measure, the amount qualifying only at an earlier decision, with no qualifying latest decision, is ours 231 length / 63 deaths; losses 103 / 35; local 889 / 283; top 2,270 / 794. This is an incremental-warning proxy, not proven incremental search benefit.
- **Remove late allied collisions from the numerator:** exclude killer on the same team at round >=300, a broad feeding proxy. Shares become ours 8.59%, losses 9.76%, local 15.24%, top 15.53%. Total-loss denominators remain unchanged. The local advantage disappears even descriptively. Allied collision lost length is ours 2,321, losses 755, local 4,565, top 6,365; the late-allied portions are 1,068, 314, 2,226 and 2,061.
- Explicit suicide counts: none in our/local cohorts, 632 top-winner deaths costing 2,132 length. Those coincide numerically with top no-valid-action losses, but intent of other cohorts' invalid actions is not inferred.
- **Wall/self alternate-step proxy:** an alternative legal direction existed in the latest-three snapshots for 5,436 of our wall/self lost length, 2,147 in our losses, 8,157 locally and 15,733 for top winners. These are separate from the killer-head criterion and do not prove the original hazard was foreseeable or that the alternative escapes the trap. The killer-head metric is not an exhaustive ceiling on all possible search gains.
- Game-resampled bootstrap of the **death-length-only** strict share (not the headline death-plus-movement denominator) gave own-minus-top 95% interval [-12.06, -1.82] percentage points, losses-minus-top [-12.19, +5.59], and local-minus-top [-3.00, +7.08]. Treat these as descriptive sensitivity: cohorts overlap on eight public games, local self-play sides are correlated, and there are only eight own losses. Do not treat thousands of dragons as independent games.

### Map breakdown
Entries are side observations: qualifying prior-3 length / **death length only**. Movement net shrink is not allocated by map in this table, so it is not the headline denominator. This exposes map mix rather than supplying a matched A/B comparison.

| Map | Our games: qualifying/death length | Top games: qualifying/death length | Local sides: qualifying/death length |
|---|---|---|---|
| Autarky | 3: 119/373 | 5: 613/2,020 | 4: 568/1,772 |
| Default | 2: 153/346 | 11: 1,100/3,593 | 4: 327/948 |
| Devil | 3: 348/3,125 | 10: 577/4,827 | 8: 2,428/9,422 |
| Prisoners Dilemma | 4: 28/947 | 7: 57/767 | 4: 30/994 |
| Portals | 3: 98/3,167 | 5: 167/5,232 | 4: 86/2,112 |
| Queen Of Spades | 3: 96/454 | 3: 25/213 | 4: 62/718 |
| Schooltime | 2: 180/988 | 11: 3,119/10,415 | 4: 1,214/5,317 |
| Slithery Fight | 3: 548/6,174 | 8: 2,031/18,098 | 4: 1,046/9,210 |
| Trauma | 2: 41/614 | 4: 247/2,905 | 8: 464/3,184 |
| Trophy | 1: 5/17 | 3: 282/560 | 4: 258/477 |

## Validation and limits
- **167/167 selected-side final total-length checks matched** the replay result.
- **2,321,879 successful movement updates**, zero reported head/neck topology mismatches, and zero unattributed collision killers.
- Independent spot check of public replay 832776 confirmed per-successful-step updates for multi-step movement; fewer updates than requested directions occurred on interrupted fatal sprints.
- This validates replay reconstruction for this S0 audit. It is not S1's simulator round-trip, does not certify every transient occupancy against an independent engine, and does not test an alternative action.
- The 67 top games are a reproducible sample of the 306 available top wins, not the entire corpus. All 26 own games were included. Top-winner selection, opponents, maps and build versions are not matched; our losses-only sample is small. Local vB19 vs related variants/self-play is a different population from ladder play.
- Knowing the eventual body owner's ID for scoring is hindsight. The visibility test uses that owner's head at the earlier decision only; it does not give the imagined policy hidden cells or future actions.
- One-step legality neither guarantees three-round survival nor positive net material after avoiding a trade. Deliberate head-on trades and feeding can inflate the apparent avoidable share. Unknown spawns, opponent responses, unseen bodies and selection policy are not simulated.
- Snapshot timing sensitivity is explicitly reported because a fatal-turn check can dominate an inclusive three-decision measure. The strict metric uses actual preceding replay rounds.
- Disk was approximately 89 MiB free when checked, substantially below the task's estimate. No generated replay/cache cleanup was needed because none was created. Only this report and the requested append to AGENT_LOG.md are written.

## Verdict
**NO-GO for proceeding from S0 on the current evidence.** Our ladder share is below the approximately 15% threshold under both timing interpretations. The local cohort clears the absolute bar but is essentially tied with top winners and fails the relative bar; the late-allied sensitivity puts it below top winners.

The earlier AGENT_LOG deadline decision also defers the full search build before the 2026-10-09 qualifiers. That schedule context is separate from this measured S0 failure. A future search proposal would need evidence for a different source of gains, or a new matched loss corpus; these measurements do not justify the planned build now. Read-only critic verdict: PASS on this S0 method and NO-GO conclusion.
