"""Game-state value from bceval (tools/battlecode-eval): each side's win probability per round.

Used two ways (RULE_MINING_SPEC.md):
  * as CONTEXT for mining: every extracted row gets p_win (the acting side's win probability at that round), so the
    contrast report compares like with like (a team that is behind feeds differently) and learning can be limited to
    positions the source team was not losing. p_win is god-view (both teams, whole map) -- never a rule feature.
  * as an EVALUATION metric: mean paired p_win at fixed rounds is a lower-variance outcome than win/loss.
bceval's own caveat applies: it cannot see the effect of one decision for ~50 rounds, so it is not a per-decision
reward. Needs pycapnp; if bceval is unavailable every function returns None and callers carry on without it.
"""
import os
import sys

_BCEVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "battlecode-eval")
if _BCEVAL not in sys.path:
    sys.path.insert(0, _BCEVAL)

try:
    from bceval import evaluate_replay, replay_features
except Exception:          # pycapnp missing, or the bceval checkout absent
    evaluate_replay = replay_features = None


def available():
    return evaluate_replay is not None


def series(path, side, every=10):
    """{round: P(side wins)} at the start of every `every`-th round, or None when bceval is unavailable."""
    if evaluate_replay is None:
        return None
    try:
        rows = evaluate_replay(path, every=every)
    except Exception:
        return None
    out = {}
    for r in rows:
        p = r["p_a"] if side == 0 else 1.0 - r["p_a"]
        out[r["after_round"] + 1] = p
    return out


def longest(path, side, every=10):
    """{round: our longest dragon on the board at the start of that round} (the queen's length), or None."""
    if replay_features is None:
        return None
    try:
        _, rows = replay_features(path, every)
    except Exception:
        return None
    return {r["round"]: r["ab"[side]]["longest"] for r in rows}


def at(ser, rnd):
    """Value at the latest evaluated round <= rnd (None if unknown)."""
    if not ser:
        return None
    best = None
    for r in ser:
        if r <= rnd and (best is None or r > best):
            best = r
    return ser[best] if best is not None else None
