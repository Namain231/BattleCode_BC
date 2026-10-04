# Antigravity queue (read this when the user says "follow the queue")

Work in this repo. Read AGENTS.md and NEXT_STEPS.md first. Do the FIRST item below whose output file does not exist yet, then append one UTF-8 line to AGENT_LOG.md and stop.

1. tools/tasks/league_build.md  -> output out/league_report.md
2. tools/tasks/farm_scale.md    -> output out/farm_report.md
3. tools/tasks/param_search.md  -> output out/param_search_report.md

Critic duty: if out/<name>_report.md exists without a matching out/<name>_critique.md, review the diff and results as CRITIC (edit nothing) and write out/<name>_critique.md ending with VERDICT: PASS or VERDICT: FAIL: <reason>.
Run Python via `uv run --python 3.11 --with unswbc python ...`. Keep C: >= 3 GB free; put data on F: (ladder/, out/ are junctions to F:).
