# Critic task for build step __NAME__ (edit NOTHING except writing out/__NAME___critique.md)

You are the CRITIC. Read AGENTS.md (Agent protocol), NEXT_STEPS.md, the brief tools/tasks/__NAME__.md and the executor's report out/__NAME___report.md, then inspect every file the report says it created or changed (use `git status --short` and `git diff` for tracked files).

Do:
1. Re-run the report's verify commands yourself (small ones only; no more than 3 parallel jobs; keep C: >= 3 GB free) and say whether the claimed numbers reproduce.
2. Attack: correctness bugs, silent failures (a failed shard counted as a loss), seed pairing mistakes, wrong side or map handling, CPU/RAM/disk risks (junctions: ladder/, out/ are on F:), anything that makes results look better than they are, missing crash-resume state, any use of an LLM inside the unattended loops (not allowed), secrets written to files.
3. Test the brief's premise: does the output actually deliver what the brief says (for the farm: >= +-1 pt precision at the stated game counts; for the league: fidelity vs the real teams' openings; for the search: no promotion without paired seeds, >= 3 pts, CPU <= 66M)?
Write out/__NAME___critique.md (<= 40 lines): required fixes with file:line, then what you would not trust. The last line must be exactly `VERDICT: PASS` or `VERDICT: FAIL: <reason>`.
