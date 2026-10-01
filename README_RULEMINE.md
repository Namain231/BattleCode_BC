# rulemine: rules from top-team replays, for gP

Implements `RULE_MINING_SPEC.md` (v2). This file is the how-to. The spec says why.

## Pieces

| Piece | What it does |
|---|---|
| `rulemine/mapgeo.py` | Map geometry: wrap, kelp, portals as teleports, and the "known terrain" rule. Unseen edges are open; a portal counts only once both ends were seen. |
| `rulemine/state.py` | Replays one game event by event. Tracks bodies, pearls and eats, plus each dragon's own memory: terrain seen since birth (a split child starts blank), teammates seen, its heads-seen-last-turn, when its length last grew. Checked against the engine's final result. |
| `rulemine/features.py` | The feature table (19 features, each defined in words). Only what the acting dragon could know on an unknown map. |
| `rulemine/decisions.py` | Opportunities and labels: `death` (feed-channel deaths beside a longer ally: invalid output, kelp, own body, or into an ally's body; `fed_ok` = the target ally ate the drops within 5 rounds, `fed_any` = any teammate did), `bud` (split at length >= 4), `queen_move` (one row per candidate step of the side's longest dragon from r250). |
| `rulemine/extract.py` | Corpus (scouting `index.json`) to CSV, in parallel. Adds `p_win` (bceval) as context. |
| `rulemine/contrast.py` | Top vs ours: decision rates per situation bucket, ranked by gap x sqrt(support); choice tendencies for queen moves. |
| `rulemine/learn.py` | Yes/no bake-off: L1-logistic and depth-3 tree ship, GBM is a ceiling check only, CV grouped by game, per-map stability. The threshold makes the rule fire about as often as the team did (at most 1.25x its rate), not at best balanced accuracy, which on a 1% decision fires many times too often. Queen moves: conditional logit, flagged DO NOT SHIP when it does not beat chance and every one-feature rule on held-out games. |
| `rulemine/codegen.py` | Model JSON to `rules_learned.hpp` (pure C++ functions, version-stamped). |
| `rulemine/evalstate.py` | bceval win probability per round: context for mining, and an evaluation metric. |
| `rulemine/evalpair.py` | Paired screen, candidate vs control on the same maps, seeds and sides: win flips + sign test, paired final-length margin (the gate), p_win and queen length at r250/400, feeds per game. |
| `rulemine/parity.py` | Python vs C++ feature parity from a logging build's replay. |
| `viper_s2_rules/` | gP (S.2) plus the hooks: `rm_hooks.hpp` (features mirrored in C++, death opportunity, queen-move utility, `LOG RMF` parity log) and knobs in `Params`: `rmDeath`, `rmQueen`, `wRmQueen`, `rmQueenFrom`, `rmLog`. With the knobs off (the default) it plays exactly like gP. |

## One cycle (48 h)

1. **Scout.** Pull fresh top-16 and own games with the existing scout tools into `ladder/scout_fresh` and `ladder/scout_self`.
2. **Extract**, top teams and ours, same definitions:
   ```
   python -m rulemine extract --index ladder/scout_fresh/index.json --root ladder/scout_fresh \
       --teams SSS,PPP,Stockfish --decision death --out rulemine_data/death_top.csv -j 10
   python -m rulemine extract --index ladder/scout_self/index.json --root ladder/scout_self \
       --decision death --out rulemine_data/death_ours.csv -j 10
   ```
3. **Contrast:** `python -m rulemine contrast --decision death --top rulemine_data/death_top.csv --ours rulemine_data/death_ours.csv --out rulemine_data/contrast_death.md`. Pick the biggest well-supported gap.
4. **Learn** per team:
   ```
   python -m rulemine learn --decision death --data rulemine_data/death_top.csv --team SSS \
       --out rulemine_data/death_SSS.json [--label fed_ok] [--min-pwin 0.4]
   ```
   Read the `.md` report next to the JSON:
   - a tree or logistic, with thresholds and support;
   - how often it fires vs how often the team did, with out-of-fold precision and recall;
   - per-map AUC (reject if `UNSTABLE`);
   - a ceiling-gap flag.

   `--label fed_ok` learns only feeds whose drops the team actually ate.
5. **Codegen:** `python -m rulemine codegen rulemine_data/death_SSS.json --out viper_s2_rules/rules_learned.hpp`. Then set the knob (`rmDeath = 1`) in a copy of `viper_s2_rules` named for the candidate.
6. **Parity:**
   - Build the candidate with `rmLog = 1` and play one game with logs (zig judge `--debug 1`).
   - Run `python -m rulemine.parity REPLAY --side A`.
   - Every feature the rule uses must be at 100%.
7. **Screen** on the farm, against the same opponent for the candidate and the control (gP or the last shipped build). Unseen sets (`--set setB`, `dev`) plus `live`:
   ```
   python tools/panel_zig.py viper_cand baselines/y8m_active runs/cand --set setB -j 10
   python tools/panel_zig.py baselines/s2_gP baselines/y8m_active runs/ctrl --set setB -j 10
   python -m rulemine.evalpair runs/cand runs/ctrl
   ```
   For big fan-outs, build a bundle with `sh farm/pack.sh OUT viper_cand baselines/s2_gP baselines/y8m_active` and see `farm/README_FARM.md`.
   This screen decides whether a candidate goes further: it needs a positive paired final margin, and must not be
   worse on `live`. Check `feeds` too: a death rule feeding several times as often as the control is misfiring on
   unseen maps (a rule fitted on 3 fixture games fed 381 times on an archipelago map vs gP's 53, and its queen
   reached length 5 by r400 vs 16). It does not replace the promotion gate in AGENTS.md: a candidate that passes the screen still
   goes through `tools/gate.py` and the ladder panel.
8. **Ladder:** a same-time A/B with a control arm (`tools/ab_ladder.py`), 25 + 25 games. Ship only if it holds.
   Never submit a build with `rmLog = 1`: the `LOG RMF` lines would publish the feature vectors in every replay.
9. **Final check** on `--set test` (the held-out `maps_rm_test`) before a tournament build.

## Tests

`python -m pytest -q tests`. The seams:
- **Extractor output** (`test_state.py`, `test_decisions.py`): the tracked final state equals the engine's result; positives match raw events; terrain is only read through the dragon's memory.
- **Feature parity** (`test_parity.py`): a replay from a `rmLog=1` build (`tests/data/parity_portals_A.replay`) must match the extractor on every feature. Regenerate it whenever `rm_hooks.hpp` or `features.py` changes: viper_s2_rules with rmLog=1 as side A vs v7.12, Portals, seed 3, `--debug 1`.
- **Learner and codegen** (`test_learn_codegen.py`): recovers known synthetic rules, and the generated C++ matches the Python reference to 1e-9.
- **End to end** (`test_cli_end_to_end.py`): extract, contrast, learn, codegen, compile; bceval symmetry; evalpair on identical games.

Replays of other teams' games stay out of git (like `ladder/`). The tests copy their four fixture replays from the local `ladder/` folder, and skip when it is absent.

## Not built yet (spec items still open)

From the spec review, 2026-10-01. Each is a follow-up, not a blocker for cycle 1 (death placement):
- **Missing features:**
  - bed-gap learning inside `state.py`, and the "local pearl flux" feature built on it;
  - the "queen intake budget" feature;
  - "travel time to the queen" as BFS over remembered terrain (`mem_top_dist` is torus Manhattan);
  - "nearest visible ally" features.
- **Queen-move model:** it fits 7 candidate-step terms, not gP's own `evaluate()` components. Fitting gP's weights
  needs those components exposed per option. The queen-move features have no parity test yet.
- **Missing hooks:** no hook for budding (`bud` is extracted and learnable, but not wired in), queen protection or
  the feeding-goal choice.
- **`evalpair` metrics:** not yet own-queen feed intake or CPU peak (the judge's figures line has the points max
  per side; `rulemine.evalpair` reads replays only). Peak with both hooks on, checked 2026-10-01: 54.3M points on
  an archipelago map, gP itself 55.7M there.
- **Runtime brake on the death rule:** the rate-matched threshold holds on the training distribution only. Each
  dragon keeps its own memory, so a swarm-wide budget is not possible; the `feeds` screen is the guard.
- **Honesty test:** the unknown-map test guards `Geo.step`. It does not replay a game with the map file withheld.
- **Queen-move features:** `toward_allies` is now one vote per visible ally (+1 closer, -1 farther); the raw
  distance sum jumped by up to the map width through a portal and dominated the fit.
- **Scope:** the spec's own-neck-only reading of the self channel is widened to any own-body hit, as the top teams'
  "own neck" channel can't be told apart in replays.

## Other evaluation tools added

| Tool | What it answers |
|---|---|
| `tools/panel_zig.py` | The local panel on the Zig judge (see step 7). |
| `tools/buildwasm.py` | Builds a bot dir to wasm, rebuilding on header edits too (unswbc's cache keys only on .cpp). |
| `farm/` | The game-farm bundle scripts (`pack.sh`, `make_jobs.py`, `run_shard.sh`, `summarize.py`, Kaggle script) and `.github/workflows/farm.yml`. |
| `tools/gen_style_maps.py` | Generated maps in all 7 Loong generator styles within the official envelope. It made `maps_rm_dev/` (tuning) and `maps_rm_test/` (held out). |
| `tools/team_mechanics.py` | Per team: sprint rate and mix, sonar pings per turn by direction, what rays hit. |
| `tools/sprint_purpose.py` | Per team: what sprints were for (kill / eat / escape / move), and deaths to enemy sprints vs single steps. |
| `tools/proto/` | Diagnostics for the throwaway `proto_rehaul` bot: death causes by intent, queen reigns. |
