# Battlecode session handoff — read this first

You are a fresh Claude Code session in this repo (`BattleCode_BC`), with no memory of
prior sessions. Your first task is **read + plan**, not to start editing code yet.

## What this project is

UNSW Battlecode "Loong" — a snake/dragon game on a torus grid. Two teams, each with
several dragons. New rules (as of 2026-10-01) changed the win condition and movement:
win is decided by queen (dragon id 0 or 1) length at round 500, then longest dragon,
then total length. Movement grants `ceil(L/4)` free sprint steps per turn based on
current length `L`. There's a per-map, per-submission ELO ladder with continuous
autoscrims.

## What's already been done (read these, in this order)

1. `research_new_meta/strategy.md`, `algorithms.md`, `strategies_followup.md`,
   `numbers.md` — prior research into pathfinding/game-AI canon and rule-specific
   math (the `d(L) = (L-1) mod 4` residue rule, strike reach, BFS validity under
   length-dependent movement, sonar for nesting/navigation, role-based strategies).
2. `research_new_meta/yvsg/REVIEW_y7_12_49.md` — code review comparing our bot
   (`baselines/s2_gP`) against a teammate's more advanced bot (`baselines/y7_12_49`).
   **Key finding, not yet acted on**: both bots share a bug where `swarmSplit()`
   (auto-budding at length >= 4) can bud the true queen (dragon 0/1) to death at
   round ~5, on any map where the queen spawns already at length > 4 (`dilemma`,
   `slithery_fight` confirmed; others may exist — check all map starting lengths).
   The fix identified: change the guard at the `swarmSplit()` call site from
   `protectedQueen()` to `(!isTrueQueen() || protectedQueen())`. Not yet applied to
   either codebase.
3. `tools/panel_zig.py` — the local panel runner (already in this repo, more
   complete than anything built this session). Usage:
   `python tools/panel_zig.py BOT_DIR OPP_DIR OUTDIR --set live|dev|test|setA|setB [--seeds 1,2] [-j N]`
   **Just patched (2026-10-01), unverified**: it now auto-detects native Windows
   and wraps the judge call through `wsl -d Ubuntu -- bash -lc ...` itself, so it
   should run straight from PowerShell without manually opening WSL first. This
   has never actually been run — see "Your first task", step 1.
4. `research_new_meta/analyze.py` — queen-rule-specific replay analyzer, run on
   `panel_zig.py`'s replay output:
   `PYTHONPATH=.:tools python research_new_meta/analyze.py OUT.json REPLAY...`
5. `tools/regression_gate.py` — standing pass/fail gate wrapping the two tools
   above: fails if win rate vs a reference opponent drops below a threshold, or
   if the candidate's queen dies before `--min-queen-round` on a game where the
   opponent's doesn't. Also unverified, also never run — see step 1.
6. `tools/queen_panel.py` — a teammate-written tool, pulled from git this session
   but not yet reviewed against your own changes above. Faster queen-death-round
   triage than `analyze.py`, but always shells through WSL regardless of host OS
   (predates panel_zig.py's auto-wrap) and hardcodes the `Ubuntu` distro name and
   judge path with no env override — confirm these match your setup before
   trusting a sweep.
7. `tools/delegate.sh` — a three-role pipeline script (you = director, `codex` =
   critic, `opencode run --model openrouter/meituan/longcat-2.0` = executor) for
   delegating a well-scoped subtask and getting a reviewed diff back. Usage:
   `tools/delegate.sh tools/task.md` (write the task file first; see the script's
   header comment for what makes a good task file). Needs Git Bash or WSL on
   Windows — won't run under plain PowerShell. **Setup is already done** on this
   machine: `opencode` and `codex` CLIs are installed, `opencode auth login` is
   already logged in to OpenRouter with a key (`secrets.env`, under `LONGCAT_API`),
   and `openrouter/meituan/longcat-2.0` is confirmed as the available slug — don't
   re-run `opencode auth login` or re-ask the user for a key. Full details (the
   role mapping, the one-time setup steps, the `opencode models openrouter` check)
   are in `AGENTS.md`'s **"Delegating to other agents"** section — read that
   before using the script, not just this bullet.
8. `baselines/s2_gP/` (ours) and `baselines/y7_12_49/` (teammate's) — only
   `main.cpp` differs between them; `maps_data.hpp`, `policy_weights.hpp`,
   `policy_nn.hpp` are byte-identical.
9. `baselines/bc-abyss-main/` — **not a teammate's code.** It's a public starter
   framework released by a different, competing team ("Cat's paradise"). Useful
   only as a reference for plumbing patterns, never as something to pull strategy
   from or assume is "ours."

Also read `claude/EVAL_TOOLS.md` if you have access to the claude.ai project this
repo is attached to (ask the user if unsure) — it documents all five eval tools
above together, including the exact validation command pair for the swarmSplit
fix (step 5 below).

## Your first task

1. **Smoke-test the eval setup before relying on it for anything else.** None of
   `panel_zig.py`'s WSL auto-wrap, `regression_gate.py`, or `queen_panel.py` have
   been run since being written/patched — this session's first job is to prove
   they actually work, not to assume they do:
   - `python tools/panel_zig.py baselines/s2_gP baselines/y7_12_49 out/smoketest --maps default --seeds 1 -j 1`
     from a plain PowerShell prompt (not already inside WSL/Git Bash) — this is
     the one that needs the new auto-wrap to work at all. If it fails, check
     `wsl -l -v` for the distro name and `WSL_DISTRO`/`PANEL_NO_WSL` env vars
     before assuming the patch is broken.
   - If that produces a real replay and `out/smoketest/summary.json`, run
     `python tools/regression_gate.py baselines/s2_gP out/gatecheck --opp baselines/y7_12_49 --maps default --seeds 1` and confirm it prints PASS/FAIL and writes
     `gate_report.json` rather than erroring on the `analyze.py` import.
   - Report exactly what broke if anything did, with the actual error — don't
     silently "fix" the scripts without saying so first, since the user will want
     to know if the WSL auto-wrap assumption was wrong on their machine.
2. **Compare speeds of three ways to run one game**, same map/seed/bots each time,
   so we know what the WSL auto-wrap actually costs (if anything) before relying
   on it for larger sweeps:
   - **Old way**: open a WSL shell yourself (`wsl -d Ubuntu`), `cd` into the repo's
     Windows path under `/mnt/c/...`, and invoke the judge binary directly (same
     command the script builds — see `tools/panel_zig.py`'s `play()` for the exact
     flags) or run `panel_zig.py` with `PANEL_NO_WSL=1` from inside that WSL shell.
   - **New way**: the patched `panel_zig.py` run straight from a plain PowerShell
     prompt (the auto-wrap from step 1).
   - **Official sandbox**: `unswbc run --sandbox maps/<map>.map <bot> <opp>` (per
     `bc-abyss-main/README.md`'s quickstart) as the baseline "intended" way to run
     a single game, for comparison against both judge-based paths above.
   - Time each with a handful of runs (`Measure-Command { ... }` in PowerShell, or
     just wall-clock a loop of 5), report the numbers, and flag anything surprising
     (e.g. if the auto-wrap adds meaningful per-call overhead vs. staying inside one
     WSL shell for a whole batch, that's worth knowing before running big sweeps
     through it).
3. Read everything in "What's already been done," in order.
4. Skim `baselines/s2_gP/main.cpp`'s queen/split logic (`protectedQueen`,
   `swarmSplit`, `trySplit`, `doomedSplit`) to confirm the bug and fix still apply
   as described (the code may have moved since this review).
5. Write a short, prioritized plan for what to do next. Candidates already on the
   table, not yet decided:
   - Apply the one-line `swarmSplit()` fix to `s2_gP` (cheap, validated root cause,
     testable immediately with `regression_gate.py` on `dilemma`/`slithery_fight`).
   - Pull `y7_12_49`'s queen architecture (separate old-election-sink vs.
     true-queen) into `s2_gP` more broadly — bigger change, higher value per
     `REVIEW_y7_12_49.md`.
   - Try the `delegate.sh` pipeline on a real task (e.g. the swarmSplit fix) to
     validate the director/critic/executor setup end-to-end.
6. Present the plan and ask which to do first — don't just pick one and start
   editing `main.cpp` unprompted, since this affects the live ladder submission.

## Context you don't have (don't guess)

- Why the user's teammate's bot is called `y7_12_49` and ours is `s2_gP` — these
  are just the directory names in `baselines/`, treat them as given.
- Any claude.ai project docs (`EVAL_TOOLS.md`, `NEW_META_FINDINGS_2026-10-01.md`,
  `RULE_CHANGES_2026-10-01.md`, `README_RULEMINE.md`) — those live in a separate
  Claude Projects workspace, not in this repo. If you need them, ask the user to
  paste them in or tell you what's missing.
