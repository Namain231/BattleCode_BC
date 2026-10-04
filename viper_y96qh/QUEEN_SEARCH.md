# Queen search: qs_fix (2026-10-04)

`viper_y96qh` is the enabled prototype; `viper_y96qh_off` has the identical
C++ sources with only Params::qSearch false. `viper_y96qh_dbg` adds QS_STATS.
No ladder submission or promotion is authorized by this work.

Safety
- qsRams enumerates every movement prefix, including legal paid steps, pearl
  growth, blocking endpoints/bodies, engine-legal reversals, oversprint death,
  and suicide. The entire path is simulated from its initial state, preserving
  the fixed free allowance. Replies are bounded to 40 and paths to 16 steps.
- Any unfinished enumeration, unknown edge, unobserved cell, insufficient
  body, imminent pearl tick, or exhausted budget discards all search results.
- qsBuild requires the whole board to be observed (at most 256 cells). This
  excludes unseen entrants instead of assuming their absence. It includes
  every observed intervening actor, including allies, in cyclic id order.
  More than three other actors or an actor capable of splitting (length >=4)
  causes fallback: this prototype does not model newborn actions.
- These deliberately strict conditions reduce coverage substantially. A lack
  of overrides is not evidence of improved queen survival.

Bounds and instrumentation
- QSClock charges at most 4000 work units per call; checks occur inside body
  reconstruction, edge/step enumeration, death loops, reply combinations and
  continuation flood fill. Copies charge cell/body sizes before allocation.
- Bodies <=64, options <=64, observed parts <=192, actors <=4 including queen;
  leaf queue/seen storage is fixed, root ranking uses three slots, and branch
  buffers are reused across siblings. No search sort or unbounded find remains.
- A secondary 2ms incremental/54ms turn guard accompanies the work budget.
  Any abort preserves the original rule option.
- QSRecord includes gates and early returns in charged/time maxima. DEBUG_QS
  emits per-call charge, zero charged overshoot, virtual ms, added points and
  abort-time overshoot; contact turns emit complete-turn time.
- QS_STATS alone emits QSS summaries at rounds divisible by 100 and at 499:
  c=calls, t=triggered, e=eligible, b=incomplete body, p=countdown <=1,
  u=unknown/view, a=budget, r=reply/path cap, x=omitted/splitting actors,
  done=completed, fatal=rule winner fatal, ov=override. Counters are per dragon.
  The two shipped arms define neither QS_STATS nor DEBUG_QS and emit no summary.

Verification
Run the commands below serially (RAM is tight):
    uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_y96qh
    uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_y96qh_off
    uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_y96qh_dbg
    uv run --python 3.11 --with unswbc python tools/qsearch_selfcheck.py
    uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qh_off baselines/Y9_6 out/qh_off_chk2 --maps maze,trauma --seeds 3 -j 1
    uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qg baselines/Y9_6 out/qg_chk2 --maps maze,trauma --seeds 3 -j 1
    uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_y96qh_dbg baselines/Y9_6 out/qh_dbg_cpu --maps australia,around_unsw --seeds 3 -j 1

The self-check compares full C++ simulator states with engine_sim: every
body/facing/alive flag, occupancy and pearls, on 240 seeded random cases and
10 hand cases. Cases include unequal head collisions (both die), own/other
tails, free/paid growth, oversprint, death pearls, kelp, wrap and portals,
paid rams and blocking sprints. Additional fixtures check all fallback gates,
reply caps, budget exhaustion and connected disjoint length-40 bodies for
three nearby enemies. Virtual milliseconds correspond to points / 1e6.
Final measured results and source hashes are in verification.json.
Not verified: full-round spawn/split parity, rescue efficacy, large paired
panels, held-out performance or ladder strength. No big panels are run here.

Final qs_fix results
- All three final WASM builds pass; arm source identity checks pass.
- 240 random + 10 hand differential cases pass, plus five fallback, one
  reply-cap, two budget-exhaustion and four adversarial checks.
- Maximum metered call: 0.264ms / 264,352 points; charged maximum 3983/4000,
  zero work overshoot. This is a tested maximum, not exhaustive timing proof.
- Maze/trauma seed 3 parity: 4 games, 551,713 identical gameplay events
  (including countdowns, sonar and indicators; CPU counters excluded).
- Debug smoke: 2/4 wins. Candidate CPU maxima: Australia A/B 64,380,280 /
  64,439,950; Around UNSW A/B 64,410,274 / 64,464,432. All <=66M.
  These values come from judge stdout: replay CPU fields are zeroed.
- Last queen snapshots (rounds 400,100,200,499): calls 397/100/200/497,
  triggered 127/17/39/58, unknown/view rejects 127/17/14/27,
  actor rejects 0/0/25/31. All other listed rejection counters, eligible,
  completed, fatal and override counts are zero at those snapshots.
  Snapshots before queen death are censored; do not treat them as final counts.
- Maximum contact-turn elapsed seen in summaries: 45.588ms; maximum call
  elapsed seen in smoke summaries: 0.008ms. Turn telemetry is sampled after
  readTurn/think/castRadar, before the small protocol-output epilogue; the
  complete-turn CPU maxima above are from the judge.
- Exact source hashes, paths and counter snapshots: verification.json.
