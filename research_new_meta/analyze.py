"""Queen/sprint metrics from replays. Usage: PYTHONPATH=repo:repo/tools python3 analyze.py OUT.json REPLAY...

Fixes/additions over the first draft (see numbers.md "What was fixed in analyze.py"):
  * moves are now bucketed PER TEAM (the draft threw both bots' moves into one list, so no sprint
    figure could be attributed to a bot). Stored as a compact Counter over (length, steps) instead
    of a per-move list, which also keeps the JSON small.
  * total team length and queen rank are recorded at every checkpoint, not just dragon counts.
  * the death list now covers every dragon with its team and reason, not only ids 0/1, so
    non-queen death rates are measurable.
  * the engine's own end-of-game counters (count/longest/total per team) are carried through so the
    recomputed tiebreak can be cross-checked against the engine.
  * per-team dragon-count / total-length series sampled every 25 rounds for trajectory plots.
"""
import sys, json, math, collections
from rulemine.state import turns, DEATHS
from replay_lite import decode_lite

def all_deaths(path):
    """(round, id, reason) for every dragonDeath, including deaths caused on another dragon's turn."""
    rd, out = 0, []
    for e in decode_lite(path, {"roundStart", "dragonDeath"})["events"]:
        if e["kind"] == "roundStart": rd = e["round"]
        else: out.append((rd, e["id"], DEATHS[e["reason"]] if e["reason"] < len(DEATHS) else "?"))
    return out

CHECK = (100, 250, 400)
SERIES = tuple(range(0, 501, 25))

def analyze(path):
    snap = collections.defaultdict(dict)     # round -> id -> pre-action length
    sprint = {0: collections.Counter(), 1: collections.Counter()}   # team -> (L, steps) -> n
    nmove = {0: 0, 1: 0}
    deaths = []                              # (round, id, team, reason, length) from the dier's own turn
    acts = []
    g = None
    for t in turns(path):
        g = t.game
        snap[t.round][t.id] = t.length
        if t.action.act == "move":
            sprint[t.team][(t.length, len(t.action.dirs))] += 1
            nmove[t.team] += 1
        if t.outcome.died:
            deaths.append((t.round, t.id, t.team, t.outcome.died, t.length)); acts.append(t.action.act)
    res = g.result
    alld = all_deaths(path)
    last = g.round
    out = {"file": path, "rounds": last + 1, "endReason": res["endReason"], "engine_winner": res["winner"],
           "engine_A": res["A"], "engine_B": res["B"], "teams": {},
           "sprint": {str(k): {f"{L},{s}": n for (L, s), n in v.items()} for k, v in sprint.items()},
           "nmove": nmove,
           "all_deaths": [(r, i, g.team.get(i, -1), why) for (r, i, why) in alld]}
    out["novalid"] = collections.Counter(a for (r, i, tm, why, L), a in zip(deaths, acts) if why in ("novalid", "?"))
    for team in (0, 1):
        q = 0 if g.team[0] == team else 1
        assert g.team[q] == team, f"{path}: dragon 0/1 are not one per team"
        row = {"queen": q}
        for r in CHECK:
            if r <= last:
                ls = {i: L for i, L in snap[r].items() if g.team[i] == team}
                row[f"q{r}"] = ls.get(q, 0)
                row[f"long{r}"] = max(ls.values(), default=0)
                row[f"rank{r}"] = 1 + sum(1 for i, L in ls.items() if L > ls.get(q, 0))
                row[f"n{r}"] = len(ls)
                row[f"total{r}"] = sum(ls.values())
        ser = []
        for r in SERIES:
            if r <= last:
                ls = {i: L for i, L in snap[r].items() if g.team[i] == team}
                ser.append((r, len(ls), sum(ls.values()), max(ls.values(), default=0), ls.get(q, 0)))
        row["series"] = ser          # (round, ndragons, total, longest, queenlen)
        alive = [i for i in g.alive if g.team[i] == team]
        row["q_end"] = g.length(q) if q in g.alive else 0
        row["long_end"] = max((g.length(i) for i in alive), default=0)
        row["total_end"] = sum(g.length(i) for i in alive)
        row["n_end"] = len(alive)
        row["q_alive_end"] = q in g.alive
        row["q_rank_end"] = 1 + sum(1 for i in alive if g.length(i) > row["q_end"])
        qd = [d for d in alld if d[1] == q]
        row["q_death"] = qd[0] if qd else None
        row["deaths_queen"] = sum(1 for (r, i, why) in alld if i == q)
        row["deaths_other"] = sum(1 for (r, i, why) in alld if i != q and g.team.get(i) == team)
        row["born"] = sum(1 for i in g.team if g.team[i] == team)
        out["teams"][team] = row
    A, B = out["teams"][0], out["teams"][1]
    def cmp(keys):
        for k in keys:
            if A[k] != B[k]:
                return (0 if A[k] > B[k] else 1), k
        return -1, "draw"
    if res["endReason"] == 1:
        out["queen_rule"] = cmp(["q_end", "long_end", "total_end"])
        out["old_rule"] = cmp(["long_end", "total_end"])
    else:
        w = 0 if A["n_end"] > 0 else 1
        out["queen_rule"] = out["old_rule"] = (w, "elim")
    return out

if __name__ == "__main__":
    res = [analyze(p) for p in sys.argv[2:]]
    json.dump(res, open(sys.argv[1], "w"))
    for r in res:
        A, B = r["teams"][0], r["teams"][1]
        print(r["file"].split("/")[-1], r["rounds"], r["endReason"], "eng", r["engine_winner"], "Q", r["queen_rule"], "old", r["old_rule"],
              "| A q", A.get("q250"), A.get("long250"), A["q_end"], A["long_end"], A["q_death"], "| B q", B.get("q250"), B.get("long250"), B["q_end"], B["long_end"], B["q_death"], "nv", dict(r["novalid"]))
