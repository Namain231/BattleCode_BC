# AGENTS.md: working in this repo

The October 2026 tournament is over; the repo is a record. If you continue the work, read `README.md` first, then
`docs/PROCESS_SUMMARY.md`, `docs/BOT_HISTORY.md` and `docs/TOOLS_AND_OPS.md` (full tool index and procedures).
Rules changed on 2026-10-01 (queen decides at round 500, dead queen = 0, free steps = ceil(L/4)); anything measured
before that date is OLD-rules evidence (see `docs/GAME_KNOWLEDGE.md`).

## Operating rules (still apply)
- **Run Python through uv:** `uv run --python 3.11 --with unswbc python tools/<script>.py` (the default Windows python can segfault on zlib).
- **Secrets:** `secrets.env` holds the Battlecode API key (`UNSWBC_KEY`) and the Kaggle token. Load with `set -a; . ./secrets.env; set +a`. Never print them, write them into files, logs or commit messages, or commit `secrets.env`.
- **Judge and panels:** `tools/panel_zig.py BOT OPP OUT --maps a,b --seeds 1,2 -j N` (Zig judge via WSL). The judge is deterministic: the same bot, seeds and sides reproduce results exactly. Local panels carry about +-5 points per 98 games and overstate strength: they screen disasters only.
- **Ladder tests:** challenges use only the ACTIVE submission (`POST /submissions/:id/activate`). Record the active id first, restore it afterwards (`tools/ab_ladder.py` does this in a `finally`), run unranked, mind the quotas (60 games per hour, 120 requests per minute, 12 uploads per hour). Always include a same-time control arm. Teammates also change the active build: re-check before and after.
- **Submitting:** `unswbc submit -n NAME -d "DESCRIPTION" DIR` uploads and activates immediately. Package only the files the bot includes (bot.toml, main.cpp, maps_data.hpp, policy_nn_v6.hpp, policy_weights_v6.hpp). Never submit with debug logging or logging of feature vectors.
- **CPU:** 100M points per dragon-turn kills the dragon. Keep measured peaks at or below about 66M; every stdout write costs 2.5M plus 4,000 per byte (`docs/SEARCH_ENGINE_CPU.md`).
- **Build cache:** `tools/buildwasm.py BOT_DIR` keys on every source file; the sandbox cache of `unswbc run --sandbox` keys on main.cpp only.
- **Windows quirks:** subprocess needs `encoding="utf-8"`; shell heredocs turn `\n` inside C++ string literals into real newlines (edit C++ with an editor); PowerShell `Out-File` writes UTF-16 (append logs with `printf >>` in Git Bash).

## Machine safety (this machine crashed from OOM once and ran out of disk repeatedly)
- Cap parallel Python jobs that load big files at 4; panels at `-j 6` alone, `-j 2-3` with other jobs; wait with `tools/mem_guard.sh MIN_MB` before heavy stages.
- Keep C: at least 3 GB free; large data belongs on the second drive (`ladder/`, `out/`, `wasm_cache/` were junctions to F:). Replay dumps fill the disk silently.
- Kill processes by explicit PID or an exact command-line match; a substring match can hit your own shell.

## Agent workflow (director / executor / critic)
- The director writes a standalone brief with an exact verify command; an executor changes only the named directory; a critic from a different back-end edits nothing and attacks both the result and the task's premise. Log every step as one line in `AGENT_LOG.md`: `- [date] [role] [task] message`.
- Back-ends: Codex CLI (`codex exec --approve-for-me "$(cat brief.md)"`, headless; usage limits and 429s happen: retry only on real error lines, not on log text that mentions "usage limit"), Antigravity IDE agent (GUI only), OpenRouter/free models for menial work. The unattended loop used here is `tools/orchestrate_build.sh` with `tools/tasks/critic_generic.md`.
- Keep example briefs in `tools/tasks/` (kamikaze, hunger, queen_search, critic_generic) as templates; the rest were pruned in the October 2026 cleanup (history in git).

## Do not
- Edit `baselines/` (frozen reference sources) or rewrite another agent's log lines.
- Trust a local percentage until the ladder confirms it; five games prove nothing.
- Leave a candidate active after a test, or start parallel jobs that starve each other of RAM.
