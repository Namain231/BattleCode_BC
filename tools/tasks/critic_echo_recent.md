# Critic task (edit NOTHING; no file writes except your final report on stdout)

You are the CRITIC for a Battlecode ("Loong") bot project. Read AGENTS.md (top sections + "Agent protocol") and the last 120 lines of AGENT_LOG.md first.
Review these items and attack their premises and methodology. For each: verdict (sound / risky / wrong), the concrete flaw with file:line, and the cheapest check that would settle it.

1. NEW: tools/echo_eval.py (offline evaluator: can 2-3 sonar rays + exact enumeration infer the first obstacle on each lane?). Result on 12 Sv5.2 ladder games:
   ray-model validation vs real sonarPing events 92.6%; 3-ray cast (drop back lane) recall 0.89 / precision 0.98, warns 7/7 queen head-on deaths in the 5 turns before death
   with 15% of turns warned; fwd-only 3/7; oracle 7/7. Assumes the kelp on the whole lane is known (map-known upper bound). Check: the 7.4% ray mismatch,
   the death-warning metric (n=7, 5-turn window, state at cast time vs echo arriving a turn later), the prior (outcome frequencies estimated on the same data),
   the policies' fairness, and whether "warned deaths" shows any lift over base rate (it needs a base-rate comparison).
2. tools/analyze_losses.py + the Sv5.2 ladder analysis (29-48): our queen died 61/77 (median round 199, 45 head-on), win 88% with queen alive vs 25% dead.
   Claim: "enclosure" shows up as an economy stall on Stripes/Tower Defense/QoS (3-4 units at r100 vs 9-15), not as wall deaths. Is the causal story supported?
3. Recent experiments (see AGENT_LOG.md, research_new_meta/*, viper_y96qf/main.cpp): queenAmputate + QBOX fallback, the CPU guard thresholds
   (elapsedMs>52 / shallow <40 / split probes 50-55), v6 net with seen-terrain weights, the 28/98-game panels (noise +-9/+-5 pts). Which conclusions are
   over-claimed? Which local-vs-ladder gaps (Sv5.1 42%, Sv5.2 29-48 on the ladder) are unexplained, and what is the single most informative next experiment?
4. Proposed (not built): queen broadcasts her position from r10-30 (signed QPOS, intent-of-direction in other rays), friends keep a zone around her and intercept
   enemy heads near her. Risks you can see (enemies read the payload? friends walling her in? unit losses from escort trades?).

Return <=40 lines: top 5 required fixes ranked, then one paragraph on what you would NOT trust yet. Last line: VERDICT: PASS or VERDICT: FAIL: <reason>.
