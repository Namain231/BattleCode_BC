# Team Bhole Chature: UNSW Battlecode ("Loong") bots

C++ dragon-snake bots for the UNSW Battlecode game, with the tooling, analysis and write-ups from the October 2026
tournament. The tournament is over; this repo is kept as a record of the method and the results.

## Read in this order

| Doc | What it covers |
|---|---|
| [docs/PROCESS_SUMMARY.md](docs/PROCESS_SUMMARY.md) | How we worked, what we built, what the data said, mistakes. Start here. |
| [docs/BOT_HISTORY.md](docs/BOT_HISTORY.md) | Every build and submission: contents, ids, results, verdicts. |
| [docs/GAME_KNOWLEDGE.md](docs/GAME_KNOWLEDGE.md) | Rules (old vs new), mechanics numbers, maps, what decides games, ladder evidence. |
| [docs/TACTICS_AND_ALGORITHMS.md](docs/TACTICS_AND_ALGORITHMS.md) | Sonar and echo, queen safety and hunt, exploration and hunger, trap detection, what failed. |
| [docs/NEURAL_NET.md](docs/NEURAL_NET.md) | Imitation nets: data, training, results, MLP student, runbook. |
| [docs/RULE_MINING.md](docs/RULE_MINING.md) | Rule mining from top-team replays: method, findings, rerun commands. |
| [docs/SEARCH_ENGINE_CPU.md](docs/SEARCH_ENGINE_CPU.md) | Search experiments, simulators and engines, CPU-points budgeting. |
| [docs/TOOLS_AND_OPS.md](docs/TOOLS_AND_OPS.md) | Setup, tool index, testing, ladder procedures, agent workflow, machine-safety lessons. |
| [docs/ORGANISER_BLOG_DIGEST.md](docs/ORGANISER_BLOG_DIGEST.md), [docs/REFERENCE_calc_writeup.md](docs/REFERENCE_calc_writeup.md) | Notes on the organisers' blog and on another team's bot design. |
| `docs/*.md` (the rest) | The official game documentation (rules, protocol, API). |
| [reports/](reports/) | The final report or critique of each October 2026 experiment, with key patches. |
| [AGENT_LOG.md](AGENT_LOG.md) | The raw chronological record of every step and decision. |

## Layout

| Path | What |
|---|---|
| `viper_y96qf`, `viper_y96qg`, `viper_nv30k`, `viper_nv30h_s4` | Sources of the builds we submitted in October 2026 (Sv5.2, Sv5.3, Sv6, Sv6h). |
| `viper_nn`, `viper_v7`, `viper_v7.12`, `viper_s2_rules` | Earlier (old-rules and rule-mining) bots. |
| `baselines/` | Frozen sources of reference builds (Y.9.6, vB.19, Nv3.0, L.10, Y.12.11, ...). |
| `tools/` | Panels, ladder A/B, replay analysis, scouting, Kaggle, orchestration scripts. |
| `ml/`, `rulemine/`, `engine_cpp/`, `farm/` | Network training, rule mining, the C++ engine copy, the game farm. |
| `maps/`, `maps_rm_dev/`, `maps_rm_test/` | Live and generated test maps. |

## Rules of thumb that survived

1. Local panels only screen out disasters (about +-5 points of noise per 98 games); the ladder with a same-time control decides.
2. Offline accuracy of an imitation net never predicted play strength.
3. Early population (units at round 100) decided most ladder games.
4. Never commit `secrets.env`; rotate the API key and Kaggle token when the event is over.

The original working notes that were merged into these docs were removed on 2026-10-14 and remain in git history (last commit containing them: `4c202f8`).
