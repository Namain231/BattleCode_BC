# Overnight loop tracker (2 Oct 2026, 07:00 -> 15:00 IST). Claude leads; user asleep.

GOAL: rank 1. Active: Y.9.5 (sub 14685). Base code: cand_y95 (= Y.9.5); rules line cand_r (no network).
Every cycle: (1) analyse each new ladder loss (queen_report, eatsrc, pair_diff, viz frames); (2) one concrete fix in
cand_sec -> regenerate rules twin; (3) test (Kaggle 80-120 paired / Colab queues jobs, jobs_b, jobs_c / laptop quick);
(4) upload + activate only if better (version names Y.9.x, then Y.10 for a big release); (5) log in LAB.md + here.

## Workers
- Codex (gpt-5.6-luna, new account, small limit): patches/audits; tasks in ladder/cosci/q_*.md.
- agy (gemini-3.8-flash-medium -> claude-sonnet-4-6 fallback): reviews, replay-reading, docs.
- opencode/LongCat: python tooling (rate-limited).
- Kaggle CPU (5 sessions) for panels; Kaggle GPU (30h/wk) / Colab GPU (jobs_c) for training; Colab CPU (jobs, jobs_b).
- Lightning: ~$5 left, reserve.

## Task board
| # | Task | Owner | Status |
|---|---|---|---|
| 1 | SEARCH1 (2-ply own search) paired Kaggle test kp1002_0605 | Kaggle | running -> decide, merge into Y.9.3 if better |
| 2 | ML audit (orientation, mirror aug, remembered-map inputs) | Codex | running (ladder/cosci/ml_audit.md) |
| 3 | S2 replay-validation harness tools/sim_validate.py | opencode | check status |
| 4 | Mid-game queen deaths vs queen-feeding teams (Schooltime: theirs fed to 67, ours dead r135) | Claude | next |
| 5 | Late feeding efficiency (Slithery 62 -> 9 units, mass lost) | Claude/agy | next |
| 6 | Dilemma/coiled economy (14 pearls r0-150) | Claude | queued |
| 7 | Retrain network: mirror aug + new-rules + generated-map data on Colab GPU (jobs_c) | Claude+Codex | after #2 |
| 8 | New maps arrive today: run on unknown maps, queen safety without KM | Claude | when maps land |

## Log
- 07:25 Y.9.2 live. Colab: jobs=SEARCH1 (s1c), jobs_b=FEED2 (cand_f2), jobs_c=FEED2 control (cand_sec). Kaggle kp1002_0605 =
  SEARCH1 vs Y.9.1 (still running). Codex: ML schema v2 Python side DONE (test_schema OK); C++ side in progress.
  Building ml/data_nr2 (schema 2, 4703 new-rules top games). agy: Dilemma opening analysis. opencode: sim_validate (slow).
- 07:50 MLV2 C++ port done by hand in cand_v2 (Codex patch was malformed; it also missed that queen gossip only starts
  at r200 -> bot assumes own queen alive before r200). Compiles with v1 weights. Dataset ml/data_nr2 (schema 2) building
  (3307 games, ~5M samples at 25%). NEXT: train nr2 (scalars 7) on Kaggle GPU/Colab GPU, export, drop header into cand_v2,
  nnSelfTest must pass, then paired panel vs cand_sec. agy Dilemma analysis retried (first reply empty).
- 08:15 SEARCH1 REJECTED (Kaggle 39/118 vs 62/120). Running: Kaggle kp1002_0745 = FEED2 vs Y.9.2 all maps (vb21, vb19,
  nick_arch4, paired, replays); Colab jobs = GROWS2 (Slithery grower from r60, L>=4) 36 games, jobs_b = its control;
  jobs_c = FEED2 control (nick_farm part). Dataset nr2 73%. agy Dilemma retried with 'no shell' instruction.
- 08:30 FEED2 Colab: 40/72 vs control 38/72 (neutral; Kaggle all-maps kp1002_0745 still running). GROWS2 Slithery
  15/36 vs control 13/36 (neutral-plus; checking in replays whether the grower actually gets longer, local 4+4 games).
  SEARCH1 TUNED (user: don't drop a good-source idea, tune it by watching games) -> cand_s1v = trap veto: 187 switches in
  163k decisions, each a real dead end; Colab jobs_b/jobs_c = s1v vs cand_sec control (vb21, vb19, all maps, 2 seeds).
  nr2 network training on Kaggle GPU (tr-nr2). agy was hung since 07:00 + a syntax slip in ask_cosci: fixed, Dilemma task
  rerun. Codex: NNFAST (identical-output net speed-up, frees CPU for search). Ladder: 4 straight ranked wins (+118).
- 09:30 Y.9.3 = Y.9.2 + QROOM + SEARCH1v uploaded and ACTIVE (14549). DILSHAFT rejected (recycled shaft deaths). GROWS2,
  NNFAST parked. Next: watch Y.9.3 ladder games; FEED2 Kaggle; nr2 network.
- 09:40 Y.9.3 ladder: 3-2 DESTINY 3 (1923, +77); 1-4 vs 1966 team (-24): 3 losses = our queen killed head-on r190-279.
  Candidates: cand_qg (QGROW: queen stops budding at 40 units/r260), cand_qh (QREACH: queen never ends within enemy
  reach+1). Local runs were killed by the harness for low memory (2 runs = 16 games at once: my mistake, keep ONE local
  run <= 10 games). Moved to Colab: jobs=qg, jobs_b=qh, jobs_c=y93 control (vb21+vb19, portals/trauma/schooltime/default,
  3 seeds, replays) batch kp1002_0908.
- 13:15 Y.9.4 (14576, QBOX) then Y.9.5 (14685 = + GROWER + PEXPLORE) released. 7 new maps in the pool (maps_new/, rebuilt
  with tools/map_from_replay.py). Rejected: FEED2, DILSHAFT, QGROW2, QREACH (parked), NNFAST (parked).
