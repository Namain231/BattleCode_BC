"""Parse a replay ONCE into a compact summary and cache it (pickle on D:), so every analysis tool can share it.

    from replay_cache import parsed
    g = parsed("path/to/game.replay")          # dict, see parse() below; cached by path + mtime
    python tools/replay_cache.py DIR_OR_GLOB    # warm the cache (prints count)

The summary keeps the bot's INTENT: every dragon's indicator tag at each turn (our bots write DOOMED/FEED/ATK/BUD/
ESCAPE-SPLIT/SHED/SPLIT/DANGER-*/L<len>... see viper_nn/main.cpp), plus its action, so tools can answer "why".
Our side: from the file name <map>_<A|B>_<seed>.replay (sandbox, tourney.py --replays) or the non-empty bot field
(ladder replays). Cache: D:/battlecode/tmp/parse_cache/<sha1>.pkl; bump VERSION when parse() changes.
"""
import collections
import glob
import hashlib
import pathlib
import pickle
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import _decode, DEATHS  # noqa: E402

VERSION = 6
CACHE = pathlib.Path("D:/battlecode/tmp/parse_cache")
DXY = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
PHASES = ((0, 50, "r0-50"), (50, 100, "r50-100"), (100, 200, "r100-200"), (200, 300, "r200-300"),
          (300, 400, "r300-400"), (400, 501, "r400+"))


def phase(r):
    for a, b, n in PHASES:
        if a <= r < b: return n
    return "r400+"


def tag_category(text):
    """Map an indicator string to a decision category."""
    if not text: return "none"
    w = text.split()[0]
    if w.startswith("DANGER-"): return "DANGER-SPLIT"
    if re.fullmatch(r"L\d+", w): return "MOVE"
    return w   # DOOMED, FEED, ATK, BUD, ESCAPE-SPLIT, SHED, SPLIT, ...


def our_side(path, rep):
    m = re.search(r"_([AB])_\d+\.replay$", str(path))
    if m: return 0 if m.group(1) == "A" else 1
    a, b = rep.get("botA"), rep.get("botB")
    return 0 if a and not b else 1 if b and not a else 0


def parse(path):
    rep = _decode(str(path))
    ours = our_side(path, rep)
    lines = rep["map"].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    name = next((l.split(" ", 1)[1] for l in lines if l.startswith("MAP_NAME")), "?")
    team, body = {}, {}
    nid = 0
    for l in lines:
        p = l.split()
        if p and p[0] == "DRAGON":
            n = int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = int(p[1]); body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]; nid += 1
    alive = set(team); pearls = set(); rnd = 0
    born = {i: 0 for i in team}
    cur_tag = {}                       # id -> latest indicator text
    dragons = {}                       # id -> info at death
    tags = collections.Counter()       # (team, phase, category) -> turns
    acts = collections.Counter()       # (team, phase, kind) -> count
    deaths = collections.Counter()     # (team, phase, cause, last tag category) -> count
    eats = collections.Counter()       # (team, phase) -> pearls eaten
    snaps = {}                         # round -> {team: (units, mass, longest)}
    heads = {}                         # round -> {team: sorted head cells}  (every 5 rounds, for divergence)
    last_act = {}
    spawn = {}                         # pearl cell -> round it appeared
    pending_wreck = {}                 # cell -> death round (wreck pearl if a pearl appears there within 2 rounds)
    wreck = set()
    M = collections.Counter()          # misc per-mechanic counters, keys (team, name) or (team, phase, name)
    def near_enemy(cell, t, r, ids=None):
        best = 99
        for j in alive:
            if team[j] == t or not body.get(j): continue
            hx, hy = body[j][0]; dx = abs(hx - cell[0]); dy = abs(hy - cell[1])
            dd = min(dx, W - dx) + min(dy, H - dy)
            if ids is not None and dd <= 2: ids.append(j)
            best = min(best, dd)
        return best
    cur_turn = None
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]; cur_turn = None
            if rnd % 10 == 0 or rnd == 499:
                s = {}
                for t in (0, 1):
                    ls = [len(body[i]) for i in alive if team[i] == t]
                    s[t] = (len(ls), sum(ls), max(ls, default=0))
                snaps[rnd] = s
            if rnd % 5 == 0:
                heads[rnd] = {t: tuple(sorted(body[i][0] for i in alive if team[i] == t and body[i])) for t in (0, 1)}
            for t in (0, 1):
                if sum(1 for i in alive if team[i] == t) >= 62: M[(t, "cap_rounds")] += 1
        elif k == "tileChange":
            t = tuple(e["tile"])
            if e.get("pearl"):
                pearls.add(t); spawn.setdefault(t, rnd)
                if t in pending_wreck and rnd - pending_wreck.pop(t) <= 2: wreck.add(t); M[("all", "wreck_made")] += 1
            else:
                if t in pearls and cur_turn is not None and cur_turn in team:
                    tm = team[cur_turn]; ph = phase(rnd)
                    eats[(tm, ph)] += 1
                    delay = rnd - spawn.get(t, rnd)
                    M[(tm, "eat_n")] += 1; M[(tm, "eat_delay_sum")] += delay
                    if delay <= 1: M[(tm, "eat_fresh")] += 1
                    if t in wreck: M[(tm, "wreck_eaten")] += 1
                    rivals = []
                    if near_enemy(t, tm, rnd, rivals) <= 2:
                        M[(tm, "eat_contested")] += 1
                        # turn order (ids act in ascending order each round): did the eater act before every nearby rival?
                        M[(tm, "race_before" if cur_turn < min(rivals) else "race_after")] += 1
                pearls.discard(t); spawn.pop(t, None); wreck.discard(t)
        elif k == "sonarPing":
            snd = e.get("sender"); M[(team.get(snd), "sonar")] += 1
            if e.get("hitKind") in ("ally", "enemy", "dragon"): M[(team.get(snd), "sonar_hit_dragon")] += 1
        elif k == "turnStart":
            cur_tag[e["id"]] = ""      # indicator (if any) arrives after turnStart, before the action
            cur_turn = e["id"]
        elif k == "dragonIndicator":
            cur_tag[e["id"]] = e.get("text", "")
        elif k == "dragonAction" and e["id"] in body and body[e["id"]] and e["id"] in team:
            i = e["id"]; t = team[i]; ph = phase(rnd); last_act[i] = e
            tags[(t, ph, tag_category(cur_tag.get(i, "")))] += 1
            act = e.get("act")
            if act == "move":
                d = e.get("dirs", "")
                acts[(t, ph, "move")] += 1
                if len(d) > 1:
                    acts[(t, ph, "sprint")] += 1; acts[(t, ph, "sprint_segs")] += len(d) - 1
                cat = tag_category(cur_tag.get(i, ""))
                if len(d) > 1:
                    # attack = ATK tag; escape = MOVE chosen with high predicted death (pd >= 0.5: the last-resort
                    # sprint options) or a DOOMED/split tag; travel = any other sprint
                    pdm = re.search(r" pd([0-9.]+)", cur_tag.get(i, "") or "")
                    esc = cat in ("DOOMED", "ESCAPE-SPLIT", "DANGER-SPLIT") or (pdm and float(pdm.group(1)) >= 0.5)
                    M[(t, ph, "sprint_" + ("attack" if cat == "ATK" else "escape" if esc else "other"))] += 1
                # eats are counted from the engine's own tileChange (pearl removed during this dragon's turn)
            elif act == "split":
                acts[(t, ph, "split1" if e.get("size") == 1 else "split")] += 1
            else:
                acts[(t, ph, str(act))] += 1
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]; hd = tuple(e["head"])
            if b[0] != hd: b.insert(0, hd)
            tl = tuple(e["tail"]) if e.get("tail") else None
            while len(b) > 1 and tl is not None and b[-1] != tl: b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]; body[e["child"]] = [tuple(x) for x in e["childBody"]]
            body[e["parent"]] = [tuple(x) for x in e["parentBody"]]; alive.add(e["child"]); born[e["child"]] = rnd
        elif k == "dragonDeath":
            i = e["id"]; alive.discard(i)
            cause = DEATHS[e["reason"]] if isinstance(e["reason"], int) and e["reason"] < len(DEATHS) else "?"
            a = last_act.get(i, {})
            deliberate = cause == "no valid action" and (a.get("act") == "suicide" or (a.get("act") == "split" and a.get("size") == 1))
            cat = tag_category(cur_tag.get(i, ""))
            t = team.get(i)
            deaths[(t, phase(rnd), "FEED" if deliberate else cause, cat)] += 1
            if cause == "head to head" and cur_turn is not None and cur_turn in team:
                # initiator = the dragon acting when the head-on happened (Codex audit: tags of the victim are stale)
                M[(t, "h2h_initiated" if team[cur_turn] == t else "h2h_received")] += 1
            if i in born and born[i] == rnd and rnd > 0: M[(t, "died_birth_round")] += 1
            for cc in (body.get(i) or [])[0::2]: pending_wreck[cc] = rnd
            dragons[i] = dict(team=t, born=born.get(i, 0), died=rnd, cause=cause, deliberate=deliberate,
                              length=len(body.get(i) or []), tag=cur_tag.get(i, ""), cell=(body[i][0] if body.get(i) else None))
    res = rep.get("result", {})
    turns = collections.Counter()
    for (t, ph, cat), v in tags.items(): turns[t] += v
    return dict(misc=dict(M), turns=dict(turns), version=VERSION, path=str(path), map=name, W=W, H=H, ours=ours, result=res,
                won=res.get("winner") == ours, end=("elim" if res.get("endReason") == 0 else "length"),
                tags=tags, acts=acts, deaths=deaths, eats=eats, snaps=snaps, heads=heads, dragons=dragons)


def parsed(path):
    p = pathlib.Path(path)
    key = hashlib.sha1(f"{p.resolve()}|{p.stat().st_mtime_ns}|{VERSION}".encode()).hexdigest()
    f = CACHE / f"{key}.pkl"
    if f.exists():
        try:
            return pickle.loads(f.read_bytes())
        except Exception:   # noqa: BLE001
            pass
    g = parse(p)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(pickle.dumps(g))
    return g


def files_of(src):
    p = pathlib.Path(src)
    return sorted(p.rglob("*.replay")) if p.is_dir() else sorted(pathlib.Path(x) for x in glob.glob(src))


if __name__ == "__main__":
    n = 0
    for f in files_of(sys.argv[1]):
        parsed(f); n += 1
    print(f"{n} replays parsed/cached")
