"""Decision definitions: when a decision was possible (opportunity) and what was done (label).

Each extractor yields dict rows: game metadata + features + label (+ outcome fields). Rows are only produced for
dragons of the chosen side. Definitions (RULE_MINING_SPEC.md, module 5):

  death  opportunity: a longer ally is visible in the window, or a teammate seen in the last 15 rounds is longer
                      and was within 6 (torus Manhattan) of my head; I am not dying to an enemy this turn.
         label:       died on its own turn by invalid output, kelp, own body, or by running into an ALLY's body
                      (the feed channels top teams use). Head-on deaths and enemy-body deaths are not opportunities.
         outcome:     fed_ok  = the target ally (the longest visible one, else the longest remembered one) ate at
                                least one of the dropped pearls within 5 rounds;
                      fed_any = any teammate did.
  bud    opportunity: length >= 4 and the team below the unit cap.
         label:       split this turn.
  queen_move          for the side's longest dragon (true length) from round 250, every single-step move:
                      one row per legal candidate step, chosen = 1 for the step taken.
"""
from . import features as F
from . import state

FEED_DEATHS = ("novalid", "wall", "self")
RECENT = 15           # rounds a teammate sighting stays in memory
OPP_RADIUS = 6        # a remembered longer teammate must have been this close (torus Manhattan)
UNIT_CAP = 64


def _meta(t, side_letter):
    g = t.game
    res = g.result or {}
    return {"game": g.game_id, "map": g.geo.name, "side": side_letter, "id": t.id, "round": t.round,
            "won": int(res.get("winner") == t.team)}


def death_rows(path, side):
    """side: 0 (A) or 1 (B)."""
    rows = []
    want = lambda g, i: g.team[i] == side

    for t in state.turns(path, want):
        s, geo = t.snapshot, t.game.geo
        died = t.outcome.died
        if died == "headon":
            continue
        into_ally = died == "body" and _hit_team(t) == side
        if died == "body" and not into_ally:
            continue
        vis = [(vl, -j, j) for (j, tm, _, vl) in s["visible"] if tm == side and vl > t.length]
        mem = [(vl, r, j) for j, (r, vl, h) in s["mates"].items()
               if t.round - r <= RECENT and vl > t.length and geo.torus_manhattan(h, s["head"]) <= OPP_RADIUS]
        if not (vis or mem):
            continue
        target = max(vis)[2] if vis else max(mem)[2]
        f = F.compute(t)
        row = _meta(t, "AB"[side])
        row.update(f)
        row["label"] = int(died in FEED_DEATHS or into_ally)
        row["target"] = target
        row["drops"] = t.outcome.drops
        rows.append(row)
    if not rows:
        return rows
    g = t.game
    eats = g.eat_log
    for row in rows:
        row["fed_ok"] = row["fed_any"] = 0
        if row["label"] and row["drops"]:
            drops, r0 = set(row["drops"]), row["round"]
            eaters = {j for (r, c, j) in eats if r0 <= r <= r0 + 5 and c in drops}
            row["fed_ok"] = int(row["target"] in eaters)
            row["fed_any"] = int(any(g.team.get(j) == side and j != row["id"] for j in eaters))
        del row["drops"]
    return rows


def _hit_team(t):
    """Team of the dragon whose body this dragon's move ran into (-1 if unknown)."""
    g, s = t.game, t.snapshot
    if t.action.act != "move" or not t.action.dirs:
        return -1
    c = s["head"]
    for ch in t.action.dirs:
        c = g.geo.step(c, "NESW".index(ch), g.known(t.id))
        if c < 0:
            return -1
        owner = s["occ"].get(c)
        if owner is not None:
            return g.team.get(owner[0], -1)
    return -1


def bud_rows(path, side):
    rows = []
    want = lambda g, i: g.team[i] == side and g.length(i) >= 4
    for t in state.turns(path, want):
        if t.snapshot["units"] >= UNIT_CAP:
            continue
        f = F.compute(t)
        row = _meta(t, "AB"[side])
        row.update(f)
        row["label"] = int(t.outcome.child >= 0)
        row["child_len"] = len(t.game.body[t.outcome.child]) if t.outcome.child >= 0 and t.outcome.child in t.game.body else 0
        rows.append(row)
    return rows


CAND = ["eat", "straight", "room_after", "d_enemy", "d_ally", "toward_allies", "enemy_reach"]


def _sign(v):
    return (v > 0) - (v < 0)


def queen_move_rows(path, side, from_round=250):
    """Long format: one row per candidate step. decision = f"{game}:{round}:{id}"."""
    rows = []

    def want(g, i):
        if g.team[i] != side or g.round < from_round:
            return False
        L = g.length(i)
        return all(g.length(j) <= L for j in g.alive if g.team[j] == side)

    for t in state.turns(path, want):
        if t.action.act != "move" or not t.action.dirs:
            continue
        g, s = t.game, t.snapshot
        geo, known, head = g.geo, g.known(t.id), s["head"]
        occ = F.known_occupancy(geo, s, head)
        facing = None
        if len(s["body"]) >= 2:
            for d in range(4):
                if geo.step(s["body"][1], d, known) == head:
                    facing = d
        chosen = "NESW".index(t.action.dirs[0])
        allies = [h for (j, tm, h, vl) in s["visible"] if tm == t.team]
        enemies = [(h, vl) for (j, tm, h, vl) in s["visible"] if tm != t.team]
        cands = []
        for d in range(4):
            n = geo.step(head, d, known)
            if n < 0 or n in occ:
                continue
            c = {"dir": d, "chosen": int(d == chosen)}
            c["eat"] = s["pearls"][n]
            c["straight"] = int(d == facing)
            c["room_after"] = F.room(geo, known, occ, n)
            c["d_enemy"] = min([geo.torus_manhattan(n, h) for h, _ in enemies] or [F.FAR])
            c["d_ally"] = min([geo.torus_manhattan(n, h) for h in allies] or [F.FAR])
            # one vote per visible ally: +1 if the step gets closer, -1 if farther. Bounded, so a portal jump (which
            # changes torus distance by up to the map width) cannot dominate the fit.
            c["toward_allies"] = sum(_sign(geo.torus_manhattan(head, h) - geo.torus_manhattan(n, h)) for h in allies)
            c["enemy_reach"] = sum(1 for h, vl in enemies if geo.torus_manhattan(n, h) <= max(1, min(vl - 1, 3)))
            cands.append(c)
        if len(cands) < 2 or not any(c["chosen"] for c in cands):
            continue
        base = _meta(t, "AB"[side])
        base["decision"] = f"{g.game_id}:{t.round}:{t.id}"
        base["len"] = t.length
        for c in cands:
            r = dict(base)
            r.update(c)
            rows.append(r)
    return rows


EXTRACTORS = {"death": death_rows, "bud": bud_rows, "queen_move": queen_move_rows}
