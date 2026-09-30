# 4. Mistakes to avoid (all measured, not guesses)

These come from real test results: our own dead ends and the earlier team builds (`v8.0-hydra`, `vB.1`–`vB.10`,
`vS.1`, `S.2`, `S.3`, `S4.4`, `S4.6`). The point isn't blame. Most of these ideas were reasonable; the
**process** let them through.

## Process mistakes (the big ones)

1. **Judging by 5 games.** The `vB` line made 10 versions in about 90 minutes, each judged on one 5-game ladder
   test. Five games can't tell a good idea from luck (see guide 3). Result: the whole `vB` line scored 4/68 on
   the ladder where V7.12 scored about 21 against the same teams.
2. **Changing many things at once.** `vB` builds changed penalties, budding, the queen and corridor rules
   together. When they lost, nobody could say which change caused it.
3. **Starting from an old version.** `v8.0` started from an older base and silently lost everything added in
   V7.9–V7.12 (short-horizon miners, even head-on trades, the late queen). **Always copy `viper_nn/`.**
4. **Skipping the gate.** None of the `vB`/`vS`/`S4` builds went through `tools/gate.py`. Head to head against
   V7.12: `vB.4` 35% on maze maps, `vB.10` 18% (0/12 on Autarky, Default, Devil and Dilemma), `vS.1` 20%.
5. **Trusting self-play alone.** A build can beat our own bots and still lose to real teams (V7.6 passed every
   local test and lost on the ladder). Only the same-time ladder A/B decides.
6. **Tuning for one map.** A rule "stop budding at round 300 on Autarky", chosen from self-play, cost games for
   several versions until it was removed. And the next phase uses **new maps**: rules keyed to a map name may
   not survive it. Test on `maps_gen/` (300 random maps) too.

## Game-logic mistakes (what the numbers showed)

| Idea | What happened |
|---|---|
| Stop budding early (round 290) | Fewer units by mid-game. Unit count is king: 6+ units ahead at round 100 wins 82% of games. |
| "Sovereign queen" (vB.7–vB.9) | The queen collapsed: final longest dragon 2–5 vs opponents' 16–29. |
| Corridor filters (vB) / choke locks (S.2) | Opening deaths from being trapped went **up**: 0.018–0.021 per dragon-turn vs V7.12's 0.012. |
| `wHunt = 0` + loss reweighting | Head-on deaths went **up** (0.009–0.015 vs 0.005–0.008). |
| Hard −45 to −60 penalties | Part of the vB bundle that scored 4/68; never tested alone, so its own effect is unknown. |
| Earlier queen (round 250) | Worse: the swarm stops growing too soon. |
| Hunting giants (test-v7.16) | 4/15 vs 3/15: no real difference. |

## What *did* work from those builds (worth reusing carefully)

- **S.2's sprint discipline**: 3–10 sprint moves per game vs V7.12's 30–56, which cost V7.12 about 40 length per
  game. S.2 won Trauma 10/12 and Portals 6/8 against V7.12.
- **S.2 / vS.1's bigger late queen**: final longest dragon grew +21 from round 300 (V7.12: +12). vS.1 went 58% on
  open maps (Portals 6/8).
- **vB.4's early expansion**: 29 units at round 100 vs V7.12's 14 against the same team.

Each of these is a good **single** change to test on top of `viper_nn/`, following guide 3.

## Things that were neutral (don't redo them expecting a gain)

Lane sonar, pearl gossip, hunting giants, soft opening safety, sonar "jamming", a bigger or more-data network,
network ensembles, copying one top team's style. See `AGENTS.md` (section 4) for the numbers.
