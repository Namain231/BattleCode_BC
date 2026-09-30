"""How a team uses sonar: volume, radar vs broadcast, direction, tail refraction, what the rays hit, and
what the 64-bit payloads encode. Run on a scout dir (with index.json) to profile the top teams.

    uv run --python 3.11 --with unswbc python tools/sonar_profile.py ladder/scout_fresh
    uv run --python 3.11 --with unswbc python tools/sonar_profile.py ladder/scout_fresh --values "cheji bt"

Mechanics this is built around (docs/sonar.md): up to four rays per turn, one per direction; a ray
stops at the first kelp or dragon part and delivers its u64 to whoever it hits, on EITHER team, with no
sender id; the sender gets back only aggregate echo counts. So one ray per turn is directional radar,
four is coarse, and a ray fired into your own body exits from the tail (rear radar).
"""
import argparse
import collections
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from replay import load  # noqa: E402

DIRS = "NESW"


def rel_dir(facing, d):
    """Ray direction relative to heading: F(orward), R(ight), B(ack), L(eft)."""
    if facing is None:
        return "?"
    k = (DIRS.index(d) - facing) % 4
    return "FRBL"[k]


def bitlen_bucket(v):
    if v == 0:
        return "0"
    b = v.bit_length()
    if b <= 8:
        return "<2^8"
    if b <= 16:
        return "<2^16"
    if b <= 32:
        return "<2^32"
    if b <= 48:
        return "<2^48"
    return ">=2^48"


def analyse(path, side, W_H_hint=None):
    rep = load(path)
    w = h = 0
    team, nid = {}, 0
    head, facing = {}, {}
    for line in rep["map"].splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "MAP":
            w, h = int(p[1]), int(p[2])
        elif p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t
            head[nid] = (c[0], c[1])
            if n > 1:  # facing from head vs neck
                dx, dy = c[0] - c[2], c[1] - c[3]
                facing[nid] = {(0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3}.get((dx, dy))
            nid += 1
    nc = w * h
    alive = set(team)
    pearls = set()
    rnd = 0
    st = collections.Counter()
    per_turn = collections.Counter()      # (round, sender) -> rays
    hits = collections.Counter()
    rel = collections.Counter()
    vals = []
    phase = collections.Counter()         # sonars by game phase
    dturns = collections.Counter()        # dragon-turns by phase
    val_is_head = val_is_pearl = val_is_round = val_cell = 0
    tail_emit = 0
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            ph = "r0-99" if rnd < 100 else "r100-299" if rnd < 300 else "r300+"
            dturns[ph] += sum(1 for i in alive if team.get(i) == side)
        elif k == "dragonUpdate" and e["head"]:
            head[e["id"]] = e["head"]
            facing[e["id"]] = e["facing"]
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            alive.add(e["child"])
            head[e["child"]] = e["childBody"][0]
            head[e["parent"]] = e["parentBody"][0]
        elif k == "dragonDeath":
            alive.discard(e["id"])
        elif k == "tileChange":
            c = e["tile"][1] * w + e["tile"][0]
            if e["pearl"]:
                pearls.add(c)
            else:
                pearls.discard(c)
        elif k == "sonarPing":
            s = e["sender"]
            if team.get(s) != side:
                continue
            st["sent"] += 1
            per_turn[(rnd, s)] += 1
            ph = "r0-99" if rnd < 100 else "r100-299" if rnd < 300 else "r300+"
            phase[ph] += 1
            hits[e["hitKind"]] += 1
            rel[rel_dir(facing.get(s), e["dir"])] += 1
            if e["origin"] is not None and head.get(s) is not None and tuple(e["origin"]) != tuple(head[s]):
                tail_emit += 1
            v = e["value"]
            vals.append(v)
            hd = head.get(s)
            hc = hd[1] * w + hd[0] if hd else -1
            if v < nc:
                val_cell += 1
                if v == hc:
                    val_is_head += 1
                if v in pearls:
                    val_is_pearl += 1
            if v == rnd or (v & 0x3FF) == (rnd & 0x3FF):
                val_is_round += 1
    return dict(st=st, per_turn=per_turn, hits=hits, rel=rel, vals=vals, phase=phase, dturns=dturns,
                val_is_head=val_is_head, val_is_pearl=val_is_pearl, val_is_round=val_is_round,
                val_cell=val_cell, tail_emit=tail_emit, nc=nc)


def entropy_bits(vals):
    """Mean per-bit entropy of the values, over 64 bits: ~1.0 per bit = random/hashed payloads."""
    if not vals:
        return float("nan")
    n = len(vals)
    tot = 0.0
    for b in range(64):
        ones = sum(1 for v in vals if (v >> b) & 1)
        p = ones / n
        if 0 < p < 1:
            tot += -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    return tot / 64


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--values", default=None, help="dump common payloads for this team (or 'ALL')")
    args = ap.parse_args()
    root = pathlib.Path(args.dir)
    # KEYED BY (teamId, game), not game alone: when two of the --top N teams play each other,
    # scout.py writes the SAME game under both teams' directories with one index.json entry each
    # (different team/side/opponent). Keying by game id alone collapses both entries to whichever
    # sorts last, silently misattributing one copy's data to the wrong team/side and losing the
    # other's entirely -- confirmed to hit 36/150 (24%) of games in the 2026-09-30 top-16 pull,
    # and it was the reason SSS's aggregate showed 0.00 sonars/dturn despite five games with
    # 35k-91k sonars each: those games' index entries were shadowed by the opponent's.
    index = {(str(e["teamId"]), str(e["game"])): e
             for e in json.load(open(root / "index.json", encoding="utf-8"))}

    agg = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    lists = collections.defaultdict(lambda: collections.defaultdict(list))
    elo = {}
    games = collections.Counter()
    for f in sorted(root.rglob("*.replay")):
        meta = index.get((f.parent.name, f.stem))
        if not meta:
            continue
        name = meta["team"]
        elo[name] = meta.get("elo")
        side = 0 if meta.get("side") in (0, "A", "a") else 1
        try:
            r = analyse(f, side)
        except Exception as exc:
            print(f"  ! {f.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        games[name] += 1
        a = agg[name]
        a["st"].update(r["st"])
        a["hits"].update(r["hits"])
        a["rel"].update(r["rel"])
        a["phase"].update(r["phase"])
        a["dturns"].update(r["dturns"])
        for kk in ("val_is_head", "val_is_pearl", "val_is_round", "val_cell", "tail_emit"):
            a["misc"][kk] += r[kk]
        for cnt in r["per_turn"].values():
            a["rays_per_turn"][cnt] += 1
        a["misc"]["active_turns"] += len(r["per_turn"])
        lists[name]["vals"] += r["vals"]

    names = sorted(agg, key=lambda n: -(elo.get(n) or 0))
    print(f"\nSonar usage, {sum(games.values())} replays, {len(names)} teams (their own dragons only)\n")
    hdr = (f"{'team':24s} {'elo':>5s} {'/dturn':>7s} {'r0-99':>6s} {'r300+':>6s} {'1ray%':>6s} {'4ray%':>6s}"
           f" {'F/R/B/L %':>15s} {'tail%':>6s} {'ally%':>6s} {'enmy%':>6s} {'kelp%':>6s} {'none%':>6s}"
           f" {'H/bit':>6s} {'cell%':>6s} {'uniq%':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for n in names:
        a = agg[n]
        sent = a["st"]["sent"]
        dt = sum(a["dturns"].values()) or 1
        rate = sent / dt
        ph0 = a["phase"]["r0-99"] / (a["dturns"]["r0-99"] or 1)
        ph2 = a["phase"]["r300+"] / (a["dturns"]["r300+"] or 1)
        rpt = a["rays_per_turn"]
        at = sum(rpt.values()) or 1
        rel = a["rel"]
        rs = sum(rel.values()) or 1
        fr = "/".join(f"{100 * rel[x] / rs:.0f}" for x in "FRBL")
        hs = a["hits"]
        hsum = sum(hs.values()) or 1
        ally = 100 * (hs["ally"] + hs["ally_head"]) / hsum
        enmy = 100 * (hs["enemy"] + hs["enemy_head"]) / hsum
        kelp = 100 * hs["kelp"] / hsum
        none_ = 100 * (hs["nothing"] + hs["empty"] + hs["unknown"]) / hsum
        v = lists[n]["vals"]
        ent = entropy_bits(v)
        cell = 100 * a["misc"]["val_cell"] / (sent or 1)
        uniq = 100 * len(set(v)) / (len(v) or 1)
        tail = 100 * a["misc"]["tail_emit"] / (sent or 1)
        print(f"{n[:24]:24s} {elo.get(n) or 0:>5d} {rate:>7.2f} {ph0:>6.2f} {ph2:>6.2f}"
              f" {100 * rpt[1] / at:>6.0f} {100 * rpt[4] / at:>6.0f} {fr:>15s} {tail:>6.0f}"
              f" {ally:>6.0f} {enmy:>6.0f} {kelp:>6.0f} {none_:>6.0f} {ent:>6.2f} {cell:>6.0f} {uniq:>6.0f}")

    print("""
Columns: /dturn = sonars per dragon-turn (max 4); r0-99 / r300+ = the same by phase; 1ray% / 4ray% = of
turns with any sonar, how many fired exactly 1 vs all 4; F/R/B/L = ray direction relative to heading;
tail% = ray emitted from somewhere other than the head (fired into own body -> exits at tail = rear radar);
ally/enmy/kelp/none = what the ray stopped on (ally incl. heads); H/bit = mean per-bit entropy of the
payloads (~1.0 = random/hashed, low = structured small numbers); cell% = payload < W*H (could be a cell
index); uniq% = distinct payloads / payloads (low = heartbeat / repeated codes).""")

    targets = names if args.values == "ALL" else ([args.values] if args.values in lists else [])
    for tname in targets:
        v = lists[tname]["vals"]
        a = agg[tname]
        if not v:
            continue
        print(f"\n=== payloads for {tname}: {len(v)} sent ===")
        print("size buckets:", dict(collections.Counter(bitlen_bucket(x) for x in v).most_common()))
        print("most common:", [(hex(x), c) for x, c in collections.Counter(v).most_common(15)])
        print(f"payload == sender head cell: {a['misc']['val_is_head']}   == a live pearl cell: "
              f"{a['misc']['val_is_pearl']}   ~ round number: {a['misc']['val_is_round']}")
        print("low 16 bits most common:", collections.Counter(x & 0xFFFF for x in v).most_common(10))
        print("high 16 bits most common:", collections.Counter(x >> 48 for x in v).most_common(10))


if __name__ == "__main__":
    main()
