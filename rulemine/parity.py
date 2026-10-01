"""Python/C++ feature parity: compare the bot's own logged feature vectors with the extractor's, turn by turn.

Build the bot with Params::rmLog = 1, play a game with logs kept (zig judge --debug 1, or unswbc run without
--sandbox caps), then:

    python -m rulemine.parity REPLAY --side A

Every "LOG RMF <round> <id> f0 f1 ..." line the bot wrote is matched with rulemine.features.compute() for the same
dragon-turn. Prints the exact-match rate per feature and the first mismatches. A learned rule may only use
features whose match rate is high; the spec's parity seam.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from replay_lite import decode_lite  # noqa: E402

from . import features as F
from . import state

TOL = 1e-6


def bot_vectors(path):
    rep = decode_lite(path, {"dragonLog"})
    out = {}
    for e in rep["events"]:
        t = e.get("text") or ""
        if t.startswith("RMF "):
            p = t.split()
            out[(int(p[1]), int(p[2]))] = [float(v) for v in p[3:]]
    return out


def compare(path, side):
    bot = bot_vectors(path)
    ids = {i for (_, i) in bot}
    stats = {n: [0, 0] for n in F.NAMES}
    examples = {}
    for t in state.turns(path, lambda g, i: g.team[i] == side and i in ids):
        key = (t.round, t.id)
        if key not in bot:
            continue
        py = F.compute(t)
        for k, n in enumerate(F.NAMES):
            ok = abs(float(py[n]) - bot[key][k]) <= TOL
            stats[n][0] += ok
            stats[n][1] += 1
            if not ok and n not in examples:
                examples[n] = (key, py[n], bot[key][k])
    return stats, examples, len(bot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--side", choices="AB", required=True)
    a = ap.parse_args()
    stats, ex, n = compare(a.replay, 0 if a.side == "A" else 1)
    print(f"{n} bot feature vectors")
    for name, (ok, tot) in stats.items():
        line = f"  {name:18s} {ok}/{tot} = {100 * ok / max(1, tot):.1f}%"
        if name in ex:
            (key, py, cpp) = ex[name]
            line += f"   first mismatch r{key[0]} id{key[1]}: python {py} vs bot {cpp}"
        print(line)


if __name__ == "__main__":
    main()
