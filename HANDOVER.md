# HANDOVER (3 Oct 2026, 00:30 IST): read this first, then AGENTS.md for rules/mechanics/tools

Team Bhole Chature (id 98), UNSW Battlecode. **Goal: rank 1.** Report times in IST. The user judges by analysis
(a few games read frame by frame) over scores, wants every ladder loss analysed, and wants ideas tuned rather than
dropped. Detail for any claim below: `research_notes/LAB.md` (dated, append-only).

## 1. State
- **Active: Y.9.6 = submission 14940**, source `bots/y96/` (= untracked `cand_y96/`). Rank **72, 1646** (was #50 1701
  at 17:00 on 2 Oct, #56 1667 that morning). Top: Cutlery 2242, horse 2198, Sponge 2165, SSS 2151, Cache me outside 2100.
- Map pool is **17 maps**: the 10 old ones + weakhold 28, Australia 29, Islands 30, Maze 31, Stripes 32,
  Tower Defense 33, Around UNSW 34 (map ids for API challenges). The bot knows only the old 10 (`KM`); new maps run
  in "unknown map" mode. Local copies with rebuilt pearl tables: `maps_new/*.map`.
- Engine 1.2.3 locally (1.2.7 is out; check the changelog before upgrading).

## 2. What Y.9.6 is (Y.9 line, all hybrid: rules + n4 network, wNN 2)
Y.9.2 SECURE (signed sonar) + QFEED from r280 + feed radius 25, floor 10 units
-> Y.9.3 **QROOM** (friends never end next to the queen's head; ladder Portals loss: 31 of our drones boxed her in)
   + **SEARCH1v** (2-ply own-move search used only as a trap veto: switches ~0.1% of moves, each a real dead end)
-> Y.9.4 **QBOX** (Schooltime ladder variant spawns the L4 queen coiled in a closed 2x2 box: she now sheds 2 instead
   of dying at r0)
-> Y.9.5 **GROWER** (protectFrom 200: the longest stops budding and grows; ladder A/B on new maps 5/15 vs 2/15) +
   **PEXPLORE** (unknown maps: hungry small drones steer to / step through unexplored portals; fixes Stripes)
-> Y.9.6 **CPUGUARD** (big new maps: long dragons spent 80-97M of 100M points scoring every free-sprint option; one
   died 'exceeded CPU limit'. Shallow eval after 45 ms, drop sprint options after 65 ms. Peak now ~72M.)

## 3. Why we lose (measured; newest first)
1. **Opening economy on mazes** (most eliminations): pearls eaten r0-150 vs top teams e.g. QoS 10 vs 147, Tower
   Defense 16 vs 117, Trophy 62 vs 239, Autarky 53 vs 193, Dilemma 37 vs 85. In paired tests EVERY flipped game was
   won by whoever ate more by r150; the opening is a chaotic race (one different move at r10 swings it).
2. **No giant when queens are dead**: most games end on longest; theirs 40-66, ours 12-30.
3. **Schooltime (2/10)**: gap opens r100-200, not the opening. They hold the 3 rich regions (548 vs 38 pearls there)
   and eat OUR dead (373 vs our 54 of theirs). Head-on is the #1 death cause both sides. (`research_notes/oc_schooltime.md`)
4. **Unknown maps**: (a) unexplored portals are walls until both ends are seen (PEXPLORE partly fixes); (b) map
   symmetry unknown (SYMMIRROR in test); (c) pocket mining: L2-3 miners die DOOMED in 1-wide pearl dead ends (Weakhold
   loss vs CookAgent), but MINEKM (no pocket exemption) LOST (see section 4): the dead ends are recycled pearls.
5. **Queen deaths**: head-on r50-150 at L2-3 (she can't outrun L2 drones; QREACH didn't help); long queens die on free
   multi-step sprints through portals into unseen bodies (QBLIND in test).
6. Slithery: both queens always die at r1 (coiled start); pure longest map; we lose 0/8 there.

## 4. Tried and why it failed (from replays, not only scores)
| Idea | Result | Mechanism found |
|---|---|---|
| FEED2 (feed only queen/elected sink, feeders <= L6) | 58/117 vs 67/116 | killed the cascade feeding that builds the 60-long giant; longest 10-25 vs 31-60. Kept: stagger + queue (FEED3) |
| QGROW2 (queen never buds, eats early) | queen alive 4/32 vs 9/32 | early deaths unchanged; L27-40 queens died late sprinting blind through portals -> QBLIND |
| QREACH (queen avoids enemy sprint reach) | 7/32 vs 9/32 alive | all her options were already in reach: an L2-3 queen can't escape |
| DILSHAFT (no L2 miners in Dilemma shafts) | 15/32 vs 19/32 | shaft deaths are recycled pearls; without them we lost more head-ons |
| GROWS2 (Slithery grower from r60) | no length gain | protection only for the elected queen; superseded by GROWER |
| SEARCH1 (2-ply search switching on score) | 39/118 vs 62/120 | leaves scored without the deep survival check (0.5 placeholder) -> noise switches; fixed as SEARCH1v veto |
| NNFAST (Codex, skip zero planes) | 57 -> 52M only | almost no plane is all-zero; needs a true sparse conv |
| Networks nm1 (scratch, new maps, local GPU) / nm2 (n4 fine-tuned) | 13/34, 18/34 vs n4 20/34 | nm1: maze openings collapse (too little data). nm2: noise; retry with more new-map games |
| MINEKM (miners respect dead ends on unknown maps) | 34/56 vs 37/56 on new maps; Weakhold 2/4 vs 4/4 | halves DOOMED deaths (11 vs 22) but the pocket deaths feed the economy (same lesson as DILSHAFT). The CookAgent Weakhold loss was the missing giant (3 vs 32) |
| Hybrid vs pure rules (1 Oct) | hybrid 45/80 vs 22/80 sandbox | the network carries the maze opening; pure-rules line is not active |

## 5. Open threads (in priority order)
1. **QBLIND** (`bots/try_qbl`: queen never takes an out-of-view move unless every in-view one is worse). Kaggle batch
   kp1002_1729 (tag qbl) vs Y.9.5: `python tools/kaggle_panel.py fetch --batch kp1002_1729`, then queen fates.
2. **FEED3** (`bots/try_f3`: cascade kept + FEED2's stagger/queue) vs Y.9.5: Kaggle batches kp1002_1738 (f3) /
   kp1002_1739 (f3base), with replays.
3. **SYMMIRROR** (`bots/try_sym`, Codex; reviewed): 21/28 vs 20/28. Resolves symmetry correctly but each dragon learns
   it alone (Maze: first at r74). Next: broadcast the resolved symmetry (2 bits in the SECURE payload).
4. **Opening economy on mazes**: the biggest gap. Ideas: hold rich regions (why does COMPASS not do it on Schooltime?),
   avoid head-ons next to their swarm (wreck denial), drop pearls outrank spawn pearls.
5. **Networks**: collector of top-15 games since the new maps (`ladder/slope_new`, restart:
   `set -a; . ./secrets.env; python -u tools/slope_collect.py --top 15 --every 20 --since 2026-10-02T06:00 --out ladder/slope_new`).
   Retrain when it has a few thousand games (local GPU, 2 min). Schema-2 (7 inputs) code is in `bots/try_v2`
   (`policy_nn.hpp` + MLV2 block in nnInput); Kaggle run `tr-nr2b` (schema 2 on old data) not yet checked.
6. Search (calc's full rollout with all dragons) needs a validated simulator first (`research_notes/SEARCH_PLAN.md`;
   opencode's `tools/sim_validate.py` unfinished).

## 6. Infrastructure (set up 2 Oct)
- **Fast judge**: over-yonder's Zig `loong-judge` in WSL2 Ubuntu (disk on D:\WSL). `tools/tourney.py` uses it by
  default when `BC_ZIG_JUDGE` is set (user env vars set; BC_JUDGE=sandbox forces the old path). Identical results,
  2.7x faster. In git-bash: `export MSYS_NO_PATHCONV=1 MSYS2_ENV_CONV_EXCL='*'` or /root paths become D:/Git/root.
  The Zig judge prints no CPU-exceeded lines: check CPU with `unswbc run ... --sandbox`.
- **Local GPU training**: WSL2 `/root/mlenv` (torch 2.6 cu124, RTX 3050 4 GB). Copy code+data into /root/work first
  (/mnt/d is slow). WSL has 7 GB: max ~380k samples per data folder (2 folders = OOM at 1.2M). Export with
  `ml/export_cpp.py` inside WSL (torch only there). Scripts: D:/battlecode/tmp/train_nm*.sh.
- **Maps from replays**: `tools/map_from_replay.py OUT.map REPLAYS...` (ladder replays zero the pearl tables; SYM env
  rot|h|v; mirrored tiles must match or the engine rejects the map).
- **Cloud**: Kaggle CPU panels `tools/kaggle_panel.py launch CAND [BASE] --panel ... --maps all|new|all17|list
  --seeds N --replays --tag T`; Colab queues `--where colab --queue jobs|jobs_b|jobs_c` (Colab results have no
  replays). Kaggle GPU training: `tools/kaggle_train.py launch --data ... --name ... --scalars 7 --schema 2`.
- **Ladder**: `tools/our_games.py --once` (downloads our games, index with played_by); `tools/upload_sub.py DIR NAME
  --champion ID` (uploads, re-activates the champion; activate the new one via API if promoting);
  `tools/top_scrims.py --interleave` (same-time A/B; it switches the active build while running).
- **Helpers**: `tools/ask_cosci.py codex|agy FILE` (Codex gpt-5.6-luna, small quota; agy Gemini 3.8 Flash -> Sonnet
  4.6; agy cannot run shell commands: tell it to use file tools only; kill a hung agy.exe if replies come back empty).
  opencode: `opencode run -m opencode/longcat-2.5-preview-free "..."` (the paid default model is out of credits).
  Codex patches often fail to apply cleanly: apply by hand and re-read.
- Memory: keep ONE local test run of <= 10 games; the harness kills background jobs under memory pressure.
  Python is at C:/Users/yoyas/AppData/Local/Programs/Python/Python312 (re-add to PATH after a session restart).

## 7. Other documents
- `AGENTS.md`: rules of the game, process, tools, pitfalls (stable). `research_notes/LAB.md`: dated log.
  `research_notes/HISTORY.md`: old-rules history. `research_notes/agy_queen.md` (how vB.21 protects its queen),
  `oc_schooltime.md`, `SEARCH_PLAN.md`, `external_writeups/calc_writeup.md` (rank-2 team's design).
- Old handovers, task boards, priority lists and pre-new-rules notes: `research_notes/archive/` (not needed).
- `HANDOFF.md`, `insights.md`, `S4_7_PLAYBOOK.md` are the teammates' (S4 line); don't edit or delete.
