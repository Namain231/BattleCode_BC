"""QoS H2H/BUD and Autarky end-freedom from n110_live replays."""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import load, DEATHS

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "replays" / "n110_live"


def our_side(fn):
    return 0 if "_as_A-" in fn.name else 1


def parse_map(rep):
    team, body, nid = {}, {}, 0
    kelp = set()
    W = H = 0
    for line in rep["map"].splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "MAP":
            W, H = int(p[1]), int(p[2])
        elif p[0] == "TILE":
            x, y, walk = int(p[1]), int(p[2]), int(p[3])
            if walk == 0:
                kelp.add((x, y))
        elif p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2])
            c = [int(v) for v in p[3 : 3 + 2 * n]]
            team[nid] = t
            body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            nid += 1
    return W, H, kelp, team, body


def flood(W, H, kelp, occ, start, neck):
    sx, sy = start
    blocked = set(occ)
    blocked.add(neck)
    q = []
    seen = set()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (sx + dx, sy + dy)
        if n[0] < 0 or n[1] < 0 or n[0] >= W or n[1] >= H:
            continue
        if n in kelp or n in blocked or n in occ:
            continue
        q.append(n)
        seen.add(n)
    i = 0
    while i < len(q) and len(seen) < 80:
        x, y = q[i]
        i += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n[0] < 0 or n[1] < 0 or n[0] >= W or n[1] >= H:
                continue
            if n in kelp or n in occ or n in seen:
                continue
            seen.add(n)
            q.append(n)
    return len(seen)


def qos_one(path, us):
    rep = load(str(path))
    W, H, kelp, team, body = parse_map(rep)
    last_ind = {}
    rnd = 0
    alive = set(team)
    units = [0, 0]
    h2h = []
    bud_near = []
    atk = []
    splits = collections.Counter()
    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]
            units = [
                sum(1 for i in alive if team.get(i) == 0),
                sum(1 for i in alive if team.get(i) == 1),
            ]
        elif k == "dragonIndicator":
            last_ind[e["id"]] = e["text"]
            tag = (e["text"].split() or ["?"])[0]
            if tag == "ATK":
                atk.append((rnd, team.get(e["id"]), e["id"], e["text"], units[0], units[1], len(body.get(e["id"], []))))
            if tag == "BUD" and team.get(e["id"]) in (0, 1):
                hid = body.get(e["id"], [(None, None)])[0]
                near = False
                for j in list(alive):
                    if team.get(j) == team.get(e["id"]):
                        continue
                    b = body.get(j)
                    if not b:
                        continue
                    hx, hy = hid
                    ex, ey = b[0]
                    if hx is None:
                        continue
                    if abs(hx - ex) + abs(hy - ey) <= 2:
                        near = True
                        break
                if near:
                    bud_near.append((rnd, team.get(e["id"]), e["id"], units[us], units[1 - us], len(body.get(e["id"], []))))
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
        elif k == "dragonSplit":
            team[e["child"]] = e["team"]
            body[e["child"]] = e["childBody"]
            body[e["parent"]] = e["parentBody"]
            alive.add(e["child"])
            splits[(e["team"], (last_ind.get(e["parent"], "?").split() or ["?"])[0])] += 1
        elif k == "dragonDeath":
            i = e["id"]
            why = DEATHS[e["reason"]] if e["reason"] < 5 else str(e["reason"])
            if why == "head to head" and team.get(i) in (0, 1):
                tag = last_ind.get(i, "")
                h2h.append((rnd, team[i], i, len(body.get(i, [])), tag[:60], units[0], units[1]))
            alive.discard(i)
            body.pop(i, None)
    return {
        "result": rep.get("result"),
        "h2h": h2h,
        "atk": atk,
        "bud_near": bud_near,
        "splits": splits,
    }


print("======== AUTARKY SPAWN FREEDOM ========")
fn = next(LIVE.glob("*autarky*as_A-seed1000.replay"))
rep = load(str(fn))
W, H, kelp, team, body = parse_map(rep)
print("map", W, H, "kelp", len(kelp))
for i, b in body.items():
    if len(b) < 8:
        continue
    occ = set(b)
    hf = flood(W, H, kelp, occ, b[0], b[1])
    tf = flood(W, H, kelp, occ, b[-1], b[-2])
    print(f"  id{i} team{team[i]} L{len(b)} head={b[0]} tail={b[-1]} headFlood={hf} tailFlood={tf} -> child should be {4 if hf>tf+1 else (len(b)-4 if tf>hf+1 else len(b)//2)}")
print("col18 walk y:", [y for y in range(H) if (18, y) not in kelp])
print("col35 walk y:", [y for y in range(H) if (35, y) not in kelp])
print("col18 kelp y:", [y for y in range(H) if (18, y) in kelp])
print("col35 kelp y:", [y for y in range(H) if (35, y) in kelp])
print("near A head (18,2):", {(x, y): ((x, y) in kelp) for x in range(16, 21) for y in range(0, 5)})
print("near A tail (18,15):", {(x, y): ((x, y) in kelp) for x in range(16, 21) for y in range(13, 18)})

print("\n======== QUEEN OF SPADES ========")
for fn in sorted(LIVE.glob("*queen_of_spades*.replay")):
    us = our_side(fn)
    d = qos_one(fn, us)
    print("\n", fn.name, "us", "AB"[us])
    print(" result", d["result"])
    us_h = [x for x in d["h2h"] if x[1] == us]
    th_h = [x for x in d["h2h"] if x[1] == 1 - us]
    print(f"  H2H deaths us {len(us_h)} them {len(th_h)}")

    def buck(rows):
        c = collections.Counter()
        for r, side, i, ln, tag, ua, ub in rows:
            ph = "0-50" if r < 50 else "50-100" if r < 100 else "100-200" if r < 200 else "200-350" if r < 350 else "350+"
            t0 = (tag.split() or ["?"])[0]
            c[f"{ph} L{ln} {t0}"] += 1
        return c.most_common(10)

    print("  our h2h", buck(us_h))
    print("  their h2h", buck(th_h))
    print("  our h2h first 10", [(r, f"L{ln}", tag[:40], f"u{ua}/{ub}") for r, _, _, ln, tag, ua, ub in us_h[:10]])
    print("  their h2h first 10", [(r, f"L{ln}", tag[:40], f"u{ua}/{ub}") for r, _, _, ln, tag, ua, ub in th_h[:10]])
    us_atk = [x for x in d["atk"] if x[1] == us]
    th_atk = [x for x in d["atk"] if x[1] == 1 - us]
    print(f"  ATK fires us {len(us_atk)} them {len(th_atk)}")
    print("  our ATK", [(r, f"L{ln}", txt, f"u{ua}/{ub}") for r, _, _, txt, ua, ub, ln in us_atk[:12]])
    print("  their ATK", [(r, f"L{ln}", txt, f"u{ua}/{ub}") for r, _, _, txt, ua, ub, ln in th_atk[:12]])
    us_bn = [x for x in d["bud_near"] if x[1] == us]
    th_bn = [x for x in d["bud_near"] if x[1] == 1 - us]
    print(f"  BUD while enemy within chebyshev/manhattan2: us {len(us_bn)} them {len(th_bn)}")
    print("  our BUD-near", us_bn[:8])
    print("  splits", dict(d["splits"]))
