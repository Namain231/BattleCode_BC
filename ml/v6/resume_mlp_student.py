"""Retired experiment entry point. Never reuse historical panel caches.

The MLP failed paired safety (50/98 versus 59/98). Original cached control
bot/engine provenance cannot be recovered. Old stage markers did not bind
maps, the actual tools/panel_zig.py, engine, analysers or output hashes.
Do not reconstruct provenance from current files or rerun this experiment.
Any future supervisor needs immutable execution-time bot/engine identities,
complete dependency/output hashes and exact unique paired map/seed/side
coverage before accepting caches. See out/mlp_student_critique.md.
"""
import sys

if __name__ == "__main__":
    print("RETIRED: mlp_student failed safety; resume and report regeneration disabled. "
          "See out/mlp_student_report.md.", file=sys.stderr)
    raise SystemExit(2)
