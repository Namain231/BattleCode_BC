# Task echo_eval_v2 (EXECUTOR). Edit ONLY tools/echo_eval.py (keep its CLI) and write results to out/echo_eval_v2.txt.

Context: tools/echo_eval.py is an offline evaluator of sonar-echo inference on real replays (Loong game, rules in docs/sonar.md, engine_sim.py board).
A critic found real flaws. Fix ALL of them, then run it and report. Read the file first. Run with:
  cd /c/Users/sohan/Downloads/BattleCode_BC; export UV_CACHE_DIR='F:\uv-cache' PYTHONIOENCODING=utf-8
  uv run --python 3.11 --with unswbc python tools/echo_eval.py ladder/sv52 --max-games 77 > out/echo_eval_v2.txt 2>&1
(Python tools must be run via uv like that. Games: ladder/sv52/games.json + .replay files. Takes ~10-20 min for 77 games; first test with --max-games 8.)

Required fixes
1. ONE record per queen turn: keep only the LAST dragonUpdate of our queen per round (sprints/splits emit several updates). Record count must be <= rounds per game.
2. Echo delay: the counts cast at round r reach the queen at her NEXT turn (r+1). Any warning derived from echoes is usable from the next queen record on; evaluate death windows accordingly
   (warning formed from record i can only be used for deaths at records > i).
3. Terrain-only kelp eligibility: whether a lane can end on kelp ("base" outcome kelp vs none) must come from tracing the ray over terrain ONLY (empty occupancy), never from the actual first obstacle.
   "Resolved by vision" = the true first obstacle (kelp or dragon) is within VIEW=3 straight steps AND the ray did not pass a portal; otherwise unresolved.
4. Ray validation: compare endpoint AND hit kind (sonarPing hitKind is relative to the sender: kelp/ally/ally_head/enemy/enemy_head) and the hit dragon id. Report match rate for each, and classify mismatches
   (via portal / via own-body refraction / sprint-reconstruction (dragon moved multiple steps in that turn) / other). If a large mismatch class is a reconstruction bug (e.g. ping state timing), fix it.
5. Held-out priors: split games into two halves by game index parity; fit outcome frequencies on one half, evaluate on the other, and vice versa; report both and the mean.
6. Fair comparison: all policies scored on the same lanes/horizon and the same FAR=12 filter for warnings (apply FAR to policy warnings as the oracle does); recall must count uncast lanes as misses ("lane coverage").
7. Baselines for the death warning (head-on queen deaths only): (a) VISION-ONLY warning (an enemy head/body in a lane within the 7x7 view, no sonar); (b) SHUFFLED baseline: circularly shift each game's warning sequence by random offsets (>= 20, 200 repetitions)
   at the same alarm rate and report the expected "deaths warned" and the lift = observed / shuffled mean (with a simple 95% interval); (c) per-turn precision P(head-on death within 5 records | warn) vs P(... | no warn).
8. New ray policies in addition to all4/three/fwd1/alt2/adapt2: fwd_rot (forward lane every turn + one side lane alternating left/right each turn), fwd_left, fwd_right, and three_nofwd_stale (three lanes cast but warnings use only the lanes not seen in view).
9. NEW reachability check (can a message channel from friends to the queen work?). On each queen record (post-move state, queen alive), for every other friendly dragon (alive, team = ours) cast its 4 rays from its head with the same ray function (own = that dragon). A message from dragon A reaches B if A's ray FIRST hit is a body part of B.
   Report overall, per phase (round <100, 100-299, >=300), per map (top maps by game count) and for the queen's death window: (a) fraction of queen records where >=1 friend has a direct ray hitting the queen; mean #friends hitting her;
   (b) fraction reached within 2 hops and 3 hops over the friend graph (edge A->B if A's ray hits B; queen as the target); (c) mean #alive friends; (d) fraction of records where an ENEMY dragon head has a direct ray hit on the queen (an enemy message could arrive);
   (e) the same (a),(b) conditioned on the queen having >=1 friend within Chebyshev distance 8.
Output: all tables printed; also write a short summary at the top of out/echo_eval_v2.txt (the script's own stdout is fine). Append ONE line to AGENT_LOG.md in UTF-8 as "- [2026-10-04] [executor] [echo_eval_v2] <what changed + headline numbers>" (use the Bash tool with printf >>, no PowerShell Out-File: it writes UTF-16).
Do NOT touch any other file. Report: files changed, headline numbers, anything you could not verify.
