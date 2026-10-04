"""Count queen-search overrides (indicator starting with QS) per replay dir: uv run ... python tools/qs_overrides.py out/qh_on"""
import sys, glob, os
sys.path.insert(0, os.path.dirname(__file__))
from replay_lite import decode_lite
for d in sys.argv[1:]:
    tot = games = 0
    for p in sorted(glob.glob(os.path.join(d, "*.replay"))):
        n = sum(1 for e in decode_lite(p, {"dragonIndicator"})["events"] if e["kind"] == "dragonIndicator" and e["text"].startswith("QS"))
        tot += n; games += n > 0
    print(f"{d}: QS overrides {tot} in {games} games with at least one")
