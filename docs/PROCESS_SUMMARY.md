# How we worked: UNSW Battlecode ("Loong") after the 2026-10-01 rules change

A short, honest account of what we tried, what the data said, and what we learned. Raw numbers and logs:
`AGENT_LOG.md` (every step), `reports/` (the final report or critique of each experiment), `research_new_meta/`
(analysis notes), `NEXT_STEPS.md` (the plan as it evolved).

## The setting
- New rules on 2026-10-01: each team has a fixed queen (dragon id 0/1); at round 500 the longer queen wins
  (a dead queen counts as 0), then the longest dragon, then total length. Free steps per turn = ceil(L/4).
- Each dragon is its own process with a 7x7 view, sonar rays for communication, and a hard CPU budget (100M points).
- The qualifiers were played on maps nobody had seen, so known-map tricks do not transfer.

## Method
- **Director / executor / critic.** One agent directs, executors write code, a critic from a different back-end
  attacks the result (Codex CLI, the Antigravity IDE agent, free models for menial work). Every task was a
  standalone brief with an exact verify command (`tools/tasks/`, `tools/delegate.sh`, `tools/orchestrate_build.sh`).
- **Local panels** (`tools/panel_zig.py`, 98 games on 7 unseen maps vs a fixed opponent) screen out disasters; they
  carry about +-5 points of noise and repeatedly overstated strength. **The ladder is the only decisive evidence.**
- **Ladder A/B** (`tools/ab_ladder.py`): same opponents and maps, back to back, with a same-time control arm.

## What we built and measured
| Area | What | Outcome |
|---|---|---|
| Replay tooling | Exact replay decoder, ray model validated against 4.2M real sonar pings (100% match), loss/queen analysers (`tools/echo_eval.py`, `analyze_ours.py`, `panel_queen.py`) | Worked; the main durable asset |
| Imitation net v6 | Conv net on top-team replays, retrained on 3,543 games (Kaggle T4); newest-game hold-out 69.85% -> 70.66% | Tiny effect; offline accuracy never predicted play |
| MLP student | 17x cheaper net (1.25M vs 21M points) at -0.6 pt accuracy | Lost 9 points of win rate: accuracy is not strength |
| Queen guard (broadcast, escort, zone, echo lanes, enemy-ping alarm) | Built after offline evaluation of echo inference and message reach | No measurable effect (59/98 -> 44/98 on fresh seeds) |
| Queen-only search | Depth-2 lookahead behind the existing trap veto | Never eligible under a 7x7 view (0 overrides); parked |
| Opening fixes (hand-coded) | Splits, cycle breaker, unwinding | Failed safety (50/98 vs 59/98) |
| Kamikaze on the enemy queen | Rams by nearby small dragons | 36/98 vs 42/98; dropped (opportunity exists in ~40% of games but is rare per game) |
| League of imitation opponents | 8 team-conditioned nets as local opponents | 0/8 faithful: Sv5.3 won 75-85% against teams that beat it every time on the ladder |
| Parameter search / farm | Automated successive halving on a local game farm | Too slow (20 h) and indirect; stopped |
| Hunger exploration | Exploration drive grows with rounds since the last pearl; strong on small maps only | Closed-start maps 29 -> 38 wins (64 games), retrace rate 34% -> 24.5%; strong hunger hurts big open maps; ladder A/B vs teammates' build: 23/48 vs 25/48 (no difference) |

## Findings that held up
1. Early population decides most ladder games (win rate 61% when ours >= theirs at r100, 22% when behind), and
   closed-start maps (Stripes, Tower Defense, Queen Of Spades, Prisoners Dilemma) were our biggest hole.
2. The queen dies in about 90% of games, but so does the enemy queen; head-on rams cause most deaths. Winners'
   economy matters more than queen survival tricks.
3. Local single-opponent panels overestimate strength (confirmed three more times); our weakest builds looked best
   against a weak yardstick.
4. The judge is deterministic: re-running the same bot and seeds reproduces results exactly, so any difference
   between two runs is a real code difference.

## Mistakes worth remembering
- Tool bugs that produced false results (a case-sensitive winner comparison gave "0/48"; a retry rule that matched
  the word "usage limit" inside logs) - verify tool output against raw records.
- Letting several agents run panels at once starved RAM and stalled the useful job; the machine ran out of disk
  repeatedly (a growing pagefile), so staging data on a second drive early is worth it.
- A long automated search was started before the measurement problem (a faithful yardstick) was solved.

## Where to start if you continue
`README.md` lists the docs. Read `docs/BOT_HISTORY.md` (what exists and how it scored), then `docs/GAME_KNOWLEDGE.md`
and `docs/TOOLS_AND_OPS.md`; `reports/` holds each experiment's verdict. The original working notes that were merged
into these docs (playbooks, handoffs, research notes, task briefs) were removed in the 2026-10-14 cleanup and remain
in git history, for example `git show 4c202f8:S4_7_PLAYBOOK.md` or `git ls-tree -r --name-only 4c202f8 research_new_meta`.
