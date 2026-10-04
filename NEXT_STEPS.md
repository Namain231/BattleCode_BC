# NEXT_STEPS (2026-10-04 22:00 IST, written by Claude whose token budget is nearly gone)

Any agent (Codex, Antigravity, OpenRouter models) can continue from here. Read AGENTS.md first, then this file.

## Why this plan
- Ladder: Sv5.2 29-48 (37.7%). Sv5.3 (id 16651, active) 58-89 (39.5%, 147 games).
- Ten iterations since Y.9.6 (queen guard, queen search, echo lanes, nets) were all within local noise. The local yardstick (98 games vs Y9_6, +-5 pts) cannot see ladder gaps: Y9_6 is stuck in the same closed starts we are.
- What decides ladder games: units at r100 (win 61% when ours >= theirs, 22% when behind); closed-start maps (Stripes, Tower Defense, Queen Of Spades, Prisoners Dilemma: 3-4 units at r100 vs 9-15 for opponents); lopsided opponents (tungtung67 0/17, Jingling Munmin 0/5).
- Public census (blog post 25): top teams first split r9 vs r21, 15 vs 9 units at r50, 2.18 vs 1.52 pearls/round, 42% of food from corpses.
- Queen-only search is parked: it is never eligible under the 7x7 view (see AGENT_LOG.md queen_search_result).
- Details: last ~40 lines of AGENT_LOG.md and research_new_meta/*.

## Jobs in flight (results land here; check DONE markers, do not re-run)
- nn_refresh3 (Codex supervisor): scouts 600 new top-team wins, builds shards_new, drift check, Kaggle fine-tune, exports candidate viper_y96qn (Sv5.2 source + new weights). Report: ladder/scout_v6/train_out/nn_refresh/report.txt, marker SUPERVISOR_DONE under ladder/scout_v6.
- opening_census: out/opening_census.txt (our opening vs top teams, closed-start recipe, ranked hypotheses). Brief: tools/tasks/opening_census.md.
- sv53_losses: out/sv53_losses.txt (why we lose to tungtung67, Jingling, etc.). Brief: tools/tasks/sv53_losses.md.

## Plan (in order; each step has a standalone brief in tools/tasks/)
1. Read the census and loss dive; pick the 5-8 opening/economy parameters or rules to test.
2. league_build.md: ladder-faithful opponent league (team-conditioned net bots for top teams, including tungtung67) so local tests resemble the ladder.
3. farm_scale.md: thousands of games per candidate on the farm bundle (WSL, Kaggle CPU kernels, GitHub Actions only with user approval) vs the league; target +-1 pt precision.
4. param_search.md: automated CMA-ES/SPRT search of opening/economy parameters on that farm. Promote only candidates that beat Sv5.3 by >= 3 pts on paired seeds vs the league AND vs Y9_6 with CPU peak <= 66M.
5. Ladder validation: submit ONE candidate (neutral name, empty description) with `unswbc submit -n NAME -d ""` (package = bot.toml, main.cpp, maps_data.hpp, policy_nn_v6.hpp, policy_weights_v6.hpp), keep it active >= 150 games, no switching, compare with Sv5.3.
- Qualifiers 2026-10-09 (unknown maps, unlimited submissions). Freeze the candidate by 10-07/08.

## Rules that bit us (also AGENTS.md "Running things safely")
- C: is nearly full (pagefile grows). Keep >= 3 GB free. Data lives on F: via junctions ladder/, out/, wasm_cache/. Old files were moved to F:\moved_from_C.
- RAM is tight: panels -j <= 6 alone, <= 3 with other jobs, use tools/mem_guard.sh.
- Run Python via `uv run --python 3.11 --with unswbc python ...`. Panels: tools/panel_zig.py. Queen and replay stats: tools/panel_queen.py, tools/analyze_ours.py (replays store our submission id in botA/botB).
- Never submit with debug logging. Never commit secrets.env, out/, ladder/.
- Real progress needs ladder evidence; local panels only screen out disasters.

## Agent lanes (token balance)
| Lane | Use for | How |
|---|---|---|
| Codex CLI (headless) | code, hard analysis, critique of diffs | `codex exec --approve-for-me "$(cat tools/tasks/X.md)" > out/X.codex.log` (retry on "model at capacity"; usage limits reset on a timer) |
| Antigravity IDE (GUI only, no headless CLI) | the same long thinking/code/critique when Codex is limited | the user opens the repo in Antigravity and tells its agent: "Follow tools/tasks/ag_queue/NEXT.md". The agent appends results to AGENT_LOG.md and writes the output file named in the brief |
| OpenRouter via opencode (`or`, longcat) | menial work: git add/commit/push/pull, downloads, file moves, log summaries | `opencode run --model openrouter/meituan/longcat-2.0 "<command-level task>"`. Never for code that changes bots |

Critique rule: whichever lane wrote code, the OTHER lane reviews the diff (Codex <-> Antigravity). Every brief states the exact verify command.
