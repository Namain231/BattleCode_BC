# NEXT_STEPS (2026-10-04 22:00 IST, written by Claude whose token budget is nearly gone)

Any agent (Codex, Antigravity, OpenRouter models) can continue from here. Read AGENTS.md first, then this file.

## UPDATE 2026-10-07 04:45 IST (user decision) - Nv3.0 is LOCKED; the goal now is to IMPROVE it
- Locked submission: Nv3.0 (id 18983, "vulture strat" = L.10 + 29-line WRECK miner targeting; source in baselines/Nv30). Early ladder: 29/67 (43%) vs mean opponent Elo 1971 (about 10 wins above Elo expectation). Do not switch the active submission without the user.
- New baseline/control for ALL local tests: baselines/Nv30 (replaces viper_y96qg/Sv5.3 as control). Cache its 98-game panel once (7 unseen maps, seeds 3-9) in out/kz_ctl and reuse it.
- Improvement jobs, in order: kamikaze (running, tools/tasks/kamikaze.md), then nv30_improve (tools/tasks/nv30_improve.md: variants from our own loss analysis, each vs the Nv30 control). Opening-fix (Sv5.3 lineage) ends 08:00 and is not rebased.
- Promotion path for any candidate: paired local panels vs Nv30 (seeds 3-9 and a confirmation set 10-16) -> critic -> a ladder A/B only with the user's approval (unranked challenges, restore Nv3.0 after).

## UPDATE 2026-10-06 18:xx IST — 3 days to qualifiers (10-09). Read this section first, it supersedes the plan below where they conflict.

**Correction:** tungtung67 (0/17 vs us) and Jingling Munmin (0/5 vs us) are both rated well above us. Treat those losses as an
ordinary skill gap, not a bug — drop `sv53_losses`'s investigation of these two matchups specifically if it hasn't already
wrapped. Don't spend further time trying to explain why we lose to them.

**Stop opening new infra fronts.** `league_build` (0/8 bots accepted as faithful), `farm_scale` (built but never ran a real
candidate selection), and `param_search` (stopped by the user as too slow/indirect after 20h) collectively spent ~2.5 days
and produced zero promoted candidates. Do not restart any of them. Two things only, in order:

1. **`mlp_student` completed: FAIL, dropped.** Export/parity/metered CPU passed; paired safety
   was 50/98 versus Sv5.3 59/98 (-9.18 pp), beyond the allowed 6-point drop.
   Keep viper_y96qm only as an unpromoted artifact; do not resume training, panels, or search.
   The unsafe cache supervisor is retired. See out/mlp_student_report.md and out/mlp_student_critique.md.
2. **Fix `viper_y96qo`'s safety regression** (`opening_recipe`, 2026-10-06: halfway test 1/4, safety 50/98 vs 59/98 FAIL, CPU
   64.648M PASS — so the failure is specifically the safety check, not CPU or the opening idea itself). This is the direct
   attempt at the biggest known gap: closed-start maps (Stripes, Tower Defense, Queen of Spades, Prisoners Dilemma), where we
   have 3-4 units at round 100 vs 9-15 for opponents, and we split round 21 vs their round 9. Iterate on the safety-check
   failure specifically; don't restart the opening design from scratch.
3. **Freeze a safe, confirmed-active submission no later than 2026-10-08, regardless of how #1/#2 go.** Confirm which of
   Sv5.2 (id 16106) or Sv5.3 (id 16651) is genuinely active on the real ladder right now — don't assume from an old log line.
   If `viper_y96qo` or the mlp_student candidate passes its checks AND clears `regression_gate.py` against the currently-active
   submission with real margin, submit that instead. Otherwise keep the current active submission and stop touching it.
   Qualifiers run on brand-new unknown maps (2026-10-09) — having *something* confirmed-active beats a better bot that's
   still mid-test when the deadline hits.

**Standing rule, reconfirmed:** don't trust any local panel number until it's validated against real ladder results. Three
separate times now (`y7_12_49`, `vB19` vs its real 8W-17L/4W-16L record, `Y9_6` vs its real Sv5.2/Sv5.3 ladder record) a local
single-opponent panel overestimated true strength by a wide margin. Every local-only percentage is provisional until the
ladder confirms it.

---

## Why this plan
- Ladder: Sv5.2 29-48 (37.7%). Sv5.3 (id 16651, active) 58-89 (39.5%, 147 games).
- Ten iterations since Y.9.6 (queen guard, queen search, echo lanes, nets) were all within local noise. The local yardstick (98 games vs Y9_6, +-5 pts) cannot see ladder gaps: Y9_6 is stuck in the same closed starts we are.
- What decides ladder games: units at r100 (win 61% when ours >= theirs, 22% when behind); closed-start maps (Stripes, Tower Defense, Queen Of Spades, Prisoners Dilemma: 3-4 units at r100 vs 9-15 for opponents); lopsided opponents (tungtung67 0/17, Jingling Munmin 0/5) — see UPDATE above, these are a skill gap, not a bug.
- Public census (blog post 25): top teams first split r9 vs r21, 15 vs 9 units at r50, 2.18 vs 1.52 pearls/round, 42% of food from corpses.
- Queen-only search is parked: it is never eligible under the 7x7 view (see AGENT_LOG.md queen_search_result).
- Details: last ~40 lines of AGENT_LOG.md and research_new_meta/*.

## Jobs in flight (results land here; check DONE markers, do not re-run)
- nn_refresh3: BLOCKED (cpu check failed, exit 1). Not resumed — superseded by mlp_student, see UPDATE above.
- league_build / farm_scale / param_search: all stopped by the user 2026-10-06, see UPDATE above. Do not restart.
- mlp_student: COMPLETED FAIL, dropped 2026-10-06; safety 50/98 vs 59/98 (-9.18 pp). Supervisor retired. See UPDATE #1.
- opening_recipe (viper_y96qo): FAILED safety 50/98 vs 59/98, CPU PASS. See UPDATE #2.

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
