"""Plane-8 sensitivity of the shipped imitation net (baselines/vB19/policy_weights.hpp).

    uv run --python 3.11 --with unswbc --with numpy python ml/p8_sensitivity.py [--every 10] REPLAY...

Numpy forward pass of the net (validated against NN_TEST_* in the weights file), states rebuilt from LOCAL replays
(exact pearlCountdown events) with ml/build_dataset.py's crop conventions, plane 8 filled four (+1) ways:
  table  : map-file gaps (known map)
  zero   : all 0 (= what vB19 itself feeds on an unseen map: it has no learnGap)
  lgap   : table value only where this dragon's learnGap (viper_b19_v4) would trust the bed (reset seen in view)
  lgapE  : as lgap but with learnGap's own estimate (gmax = max countdown seen, gmin = min fresh draw or 1)
  first  : table value for every bed this dragon has ever had in its 7x7 view
Per-dragon memory: each dragon (incl. children) starts empty and updates at each of its own turns.
No pickle cache is written. Prints a JSON summary.
"""
import argparse
import gzip
import json
import pathlib
import re
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ml"))
from build_dataset import parse_map, OFF, VIEW, S, DXY, DIRS  # noqa: E402
from replay import Msg, unpack, point, EVENT_KINDS  # noqa: E402

VARIANTS = ["table", "zero", "lgap", "lgapE", "first"]


# ------------------------------------------------------------------ network --
def load_weights(path):
    txt = open(path, encoding="utf-8").read()
    W = {}
    for m in re.finditer(r"static const (float|unsigned char) (\w+)\[(\d+)\] = \{([^}]*)\};", txt):
        arr = np.array([float(v.rstrip("f")) for v in m.group(4).split(",")], np.float32)
        assert len(arr) == int(m.group(3)), m.group(2)
        W[m.group(2)] = arr
    C = 32
    W["c1"] = W["NN_C1_WEIGHT"].reshape(C, -1); W["c2"] = W["NN_C2_WEIGHT"].reshape(C, -1)
    W["c3"] = W["NN_C3_WEIGHT"].reshape(C, -1)
    W["fc"] = W["NN_FC_WEIGHT"].reshape(64, -1); W["out"] = W["NN_OUT_WEIGHT"].reshape(6, -1)
    return W


def conv3(x, w, b):
    """x (B,IC,N,N), w (OC, IC*9) in [oc][ic][ky][kx] order, padding 1 -> (B,OC,N,N)."""
    B, IC, N, _ = x.shape
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    cols = np.stack([xp[:, :, ky:ky + N, kx:kx + N] for ky in range(3) for kx in range(3)], 2)  # B,IC,9,N,N
    return np.einsum("bkn,ok->bon", cols.reshape(B, IC * 9, N * N), w, optimize=True).reshape(B, -1, N, N) \
        + b[None, :, None, None]


def forward(W, planes, scal):
    """planes (B,16,15,15) uint8, scal (B,3) float -> logits (B,6). Mirrors policy_nn.hpp / train.py Policy."""
    B = planes.shape[0]
    x = np.concatenate([planes.astype(np.float32) / 255.0,
                        np.broadcast_to(scal[:, :, None, None], (B, 3, S, S))], 1)
    a1 = np.maximum(conv3(x, W["c1"], W["NN_C1_BIAS"]), 0)
    p1 = a1[:, :, :14, :14].reshape(B, 32, 7, 2, 7, 2).mean((3, 5))
    a2 = np.maximum(conv3(p1, W["c2"], W["NN_C2_BIAS"]), 0)
    a3 = np.maximum(conv3(a2, W["c3"], W["NN_C3_BIAS"]) + a2, 0)
    h = np.maximum(a3.reshape(B, -1) @ W["fc"].T + W["NN_FC_BIAS"], 0)
    return np.concatenate([h, scal], 1) @ W["out"].T + W["NN_OUT_BIAS"]


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


# ------------------------------------------------------------------ replays --
def iter_events(path):
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    root = Msg(unpack(raw)).struct(0, 0)
    yield {"kind": "map", "text": root.text(0)}
    for ev in root.structs(3):
        kind = EVENT_KINDS[ev.u16(0)]
        if kind not in ("roundStart", "turnStart", "pearlCountdown", "tileChange", "dragonAction",
                        "dragonUpdate", "dragonSplit", "dragonDeath"):
            continue
        b = ev.struct(0)
        e = {"kind": kind}
        if b is None:
            continue
        if kind == "roundStart":
            e["round"] = b.i32(0)
        elif kind in ("turnStart", "dragonDeath"):
            e["id"] = b.i32(0)
        elif kind == "pearlCountdown":
            e["value"] = b.i32(0); e["tile"] = point(b.struct(0))
        elif kind == "tileChange":
            e["tile"] = point(b.struct(0)); e["pearl"] = b.bit(0)
        elif kind == "dragonUpdate":
            e["id"] = b.i32(0); e["facing"] = b.u16(4)
            e["head"] = point(b.struct(0)); e["tail"] = point(b.struct(1))
        elif kind == "dragonSplit":
            e["parent"] = b.i32(0); e["child"] = b.i32(4); e["team"] = b.u16(8)
            e["parentBody"] = [point(p) for p in b.structs(0)]
            e["childBody"] = [point(p) for p in b.structs(1)]
        elif kind == "dragonAction":
            e["id"] = b.i32(0)
            act = b.struct(0)
            if act:
                w = act.u16(0)
                e["act"] = ["move", "split", "suicide"][w] if w < 3 else w
                if w == 0 and act.ptr(0):
                    lst = act.m.list(*act.ptr(0))
                    if lst:
                        s, start, _, count = lst
                        raw16 = act.m.segs[s][start * 8:start * 8 + 2 * count]
                        e["dirs"] = "".join(DIRS[int.from_bytes(raw16[2 * k:2 * k + 2], "little") % 4]
                                            for k in range(count))
        yield e


def rate8(lo, hi):
    return np.where(hi > 0, np.minimum(255, (255.0 * 2.0 / np.maximum(1, lo + hi) * 4).astype(np.int64)), 0)


class Mem:
    """One dragon's own knowledge (starts empty, children too)."""
    def __init__(self, H, W):
        self.last = np.full((H, W), -1, np.int32)     # round it last had the cell in view
        self.cyc = np.zeros((H, W), np.int16)         # resets seen (learnGap ptCycles)
        self.ptmax = np.zeros((H, W), np.int32)
        self.fresh = np.zeros((H, W), np.int32)       # smallest fresh draw (0 = none)
        self.seen = np.zeros((H, W), bool)


def run_game(path, every, Wn):
    it = iter_events(path)
    text = next(it)["text"]
    name, W, H, kelp, portal, rate = parse_map(text)
    team, body, facing, nid = {}, {}, {}, 0
    for l in text.splitlines():
        p = l.split()
        if p and p[0] == "DRAGON":
            t, n = int(p[1]), int(p[2]); c = [int(v) for v in p[3:3 + 2 * n]]
            team[nid] = t; body[nid] = [(c[2 * i], c[2 * i + 1]) for i in range(n)]
            (hx, hy), (nx, ny) = body[nid][0], body[nid][1]
            dx, dy = (hx - nx + W // 2) % W - W // 2, (hy - ny + H // 2) % H - H // 2
            facing[nid] = DXY.index((int(np.sign(dx)), int(np.sign(dy)))) if (dx == 0) != (dy == 0) else 0
            nid += 1
    alive = set(team)
    mem = {i: Mem(H, W) for i in team}
    pearls = np.zeros((H, W), np.uint8)
    cd_val = np.full((H, W), -1, np.int32); cd_rnd = np.zeros((H, W), np.int32)
    reset_rnd = np.full((H, W), -1, np.int32)
    rnd, started = 0, False
    vdy, vdx = np.meshgrid(np.arange(-3, 4), np.arange(-3, 4), indexing="ij")
    vdy, vdx = vdy.ravel(), vdx.ravel()
    pend = None
    P, SC, P8, Y, META = [], [], [], [], []
    for e in it:
        k = e["kind"]
        if k == "roundStart":
            rnd = e["round"]; started = True
        elif k == "pearlCountdown":
            (x, y) = e["tile"]; x %= W; y %= H
            cd_val[y, x] = e["value"]; cd_rnd[y, x] = rnd
            if started:
                reset_rnd[y, x] = rnd
        elif k == "turnStart":
            pend = None
            i = e["id"]
            if i not in alive:
                continue
            m = mem.setdefault(i, Mem(H, W))
            hx, hy = body[i][0]
            vy, vx = (hy + vdy) % H, (hx + vdx) % W
            bed = cd_val[vy, vx] >= 0
            pt = np.where(bed, cd_val[vy, vx] - (rnd - cd_rnd[vy, vx]), -1)
            last = m.last[vy, vx]
            reset = bed & (last >= 0) & (reset_rnd[vy, vx] > last)
            m.cyc[vy, vx] += reset
            dt1 = reset & (last == rnd - 1)
            fr = m.fresh[vy, vx]
            m.fresh[vy, vx] = np.where(dt1 & ((fr <= 0) | (pt + 1 < fr)), pt + 1, fr)
            m.ptmax[vy, vx] = np.maximum(m.ptmax[vy, vx], pt)
            m.last[vy, vx] = rnd
            m.seen[vy, vx] = True
            if rnd % every == 0:
                pend = (i, snapshot(i, team, body, facing, alive, pearls, kelp, portal, rate, m, rnd, W, H))
        elif k == "dragonAction" and pend and e["id"] == pend[0]:
            i, (planes, scal, p8, f) = pend
            act = e.get("act")
            if act == "move" and e.get("dirs"):
                y = (DIRS.index(e["dirs"][0]) - f) % 4
            elif act == "split":
                y = 4
            else:
                y = 5
            P.append(planes); SC.append(scal); P8.append(p8); Y.append(y); META.append((rnd, team[i]))
            pend = None
        elif k == "tileChange":
            (x, y) = e["tile"]; pearls[y % H, x % W] = 1 if e["pearl"] else 0
        elif k == "dragonUpdate" and e["id"] in body and e["head"]:
            b = body[e["id"]]
            if b[0] != e["head"]:
                b.insert(0, e["head"])
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
            (x, y) = e["head"]; pearls[y % H, x % W] = 0
            facing[e["id"]] = e["facing"] % 4
        elif k == "dragonSplit":
            c = e["child"]
            team[c] = e["team"]; body[c] = e["childBody"]; body[e["parent"]] = e["parentBody"]
            alive.add(c); mem[c] = Mem(H, W)
            cb = e["childBody"]
            if len(cb) >= 2:
                (hx, hy), (nx, ny) = cb[0], cb[1]
                dx, dy = (hx - nx + W // 2) % W - W // 2, (hy - ny + H // 2) % H - H // 2
                if (dx == 0) != (dy == 0):
                    facing[c] = DXY.index((int(np.sign(dx)), int(np.sign(dy))))
        elif k == "dragonDeath":
            alive.discard(e["id"]); mem.pop(e["id"], None)
    if not Y:
        return None
    return name, np.stack(P), np.stack(SC), np.stack(P8), np.array(Y), np.array(META)


def snapshot(i, team, body, facing, alive, pearls, kelp, portal, rate, m, rnd, W, H):
    """build_dataset.snapshot (16 planes, first 3 scalars) + plane-8 variants."""
    own = np.zeros((H, W), np.uint8); ally = own.copy(); enemy = own.copy(); ahead = own.copy(); ehead = own.copy()
    for j in alive:
        b = body[j]; L = len(b)
        tgt = own if j == i else ally if team[j] == team[i] else enemy
        for k, (x, y) in enumerate(b):
            tgt[y % H, x % W] = min(255, (L - k) * 16)
        if j != i:
            (x, y) = b[0]
            (ahead if team[j] == team[i] else ehead)[y % H, x % W] = min(255, L * 8)
    f = facing.get(i, 0)
    hx, hy = body[i][0]
    ox, oy = OFF[f]
    xs, ys = (hx + ox) % W, (hy + oy) % H
    planes = np.zeros((16, S, S), np.uint8)
    for r in range(4):
        planes[r] = kelp[ys, xs, (r + f) % 4] * 255
        planes[4 + r] = portal[ys, xs, (r + f) % 4] * 255
    planes[9] = VIEW * 255
    for c, arr in ((10, pearls * 255), (11, own), (12, ally), (13, enemy), (14, ahead), (15, ehead)):
        planes[c] = np.where(VIEW, arr[ys, xs], 0)
    units = sum(1 for j in alive if team[j] == team[i])
    scal = np.array([len(body[i]) / 32, rnd / 500, units / 64], np.float32)
    tab = rate[ys, xs]
    learned = m.cyc[ys, xs] >= 1
    gmax = np.maximum(1, m.ptmax[ys, xs]); fr = m.fresh[ys, xs]
    gmin = np.where(fr > 0, np.minimum(fr, gmax), 1)
    est = np.where(learned, rate8(gmin, gmax), 0)
    p8 = np.stack([tab, np.zeros_like(tab), np.where(learned, tab, 0), est, np.where(m.seen[ys, xs], tab, 0)])
    return planes, scal, p8.astype(np.uint8), f


# ------------------------------------------------------------------ metrics --
def evaluate(W, P, SC, P8, Y, batch=512):
    probs = {v: [] for v in VARIANTS}
    for s in range(0, len(Y), batch):
        pl = P[s:s + batch].copy()
        for vi, v in enumerate(VARIANTS):
            pl[:, 8] = P8[s:s + batch, vi]
            probs[v].append(softmax(forward(W, pl, SC[s:s + batch])))
    return {v: np.concatenate(probs[v]) for v in VARIANTS}


def summarize(pr, Y, sel):
    n = int(sel.sum())
    out = {"n": n}
    pt = pr["table"][sel]
    at = pt.argmax(1); at4 = pt[:, :4].argmax(1)
    out["acc_table_vs_label"] = float((at == Y[sel]).mean())
    mv = Y[sel] < 4
    out["acc4_table_vs_move_label"] = float((at4[mv] == Y[sel][mv]).mean()) if mv.any() else None
    for v in VARIANTS:
        q = pr[v][sel]
        kl = (pt * (np.log(pt + 1e-12) - np.log(q + 1e-12))).sum(1)
        out[v] = {"flip6": float((q.argmax(1) != at).mean()),
                  "flip4": float((q[:, :4].argmax(1) != at4).mean()),
                  "kl": float(kl.mean()), "kl_p95": float(np.percentile(kl, 95)),
                  "maxp": float(q.max(1).mean()),
                  "acc": float((q.argmax(1) == Y[sel]).mean())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replays", nargs="+")
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--weights", default=str(ROOT / "baselines/vB19/policy_weights.hpp"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    Wn = load_weights(a.weights)
    tp = Wn["NN_TEST_PLANES"].astype(np.uint8).reshape(1, 16, S, S)
    lg = forward(Wn, tp, Wn["NN_TEST_SCALARS"].reshape(1, 3))[0]
    print("selftest logits", np.round(lg, 4).tolist(), "ref", np.round(Wn["NN_TEST_LOGITS"], 4).tolist(),
          "maxabs", float(np.abs(lg - Wn["NN_TEST_LOGITS"]).max()), flush=True)
    Ps, SCs, P8s, Ys, Gs, Ks = [], [], [], [], [], []
    for gi, path in enumerate(a.replays):
        r = run_game(path, a.every, Wn)
        if r is None:
            continue
        name, P, SC, P8, Y, META = r
        Ps.append(P); SCs.append(SC); P8s.append(P8); Ys.append(Y)
        Gs.append(np.full(len(Y), gi)); Ks.append(np.full(len(Y), "generated" in path or "maps_rm" in path))
        print(f"{path}: {name} {len(Y)} states", flush=True)
    P, SC, P8, Y = np.concatenate(Ps), np.concatenate(SCs), np.concatenate(P8s), np.concatenate(Ys)
    gen = np.concatenate(Ks)
    del Ps, P8s
    pr = evaluate(Wn, P, SC, P8, Y)
    s4 = pr["table"][:, :4].sum(1, keepdims=True)
    print("4-move renormalised sums to 1:", bool(np.allclose((pr["table"][:, :4] / s4).sum(1), 1)),
          "6-class sums to 1:", bool(np.allclose(pr["table"].sum(1), 1)))
    tab = P8[:, 0]
    nz = tab[tab > 0]
    med = float(np.median(nz)) if len(nz) else 0.0
    fast = (tab > med).reshape(len(Y), -1).any(1)
    anybed = (tab > 0).reshape(len(Y), -1).any(1)
    res = {"median_nonzero_plane8": med, "label_counts": np.bincount(Y, minlength=6).tolist()}
    for nm, sel in (("all", np.ones(len(Y), bool)), ("fast_bed_in_crop", fast), ("any_bed_in_crop", anybed),
                    ("live_maps", ~gen), ("generated_maps", gen), ("live_fast", ~gen & fast),
                    ("generated_fast", gen & fast)):
        if sel.any():
            res[nm] = summarize(pr, Y, sel)
    # coverage of fast-bed crop cells by each variant
    fc = tab > med
    res["fast_cell_coverage"] = {v: float((P8[:, vi][fc] > 0).mean()) for vi, v in enumerate(VARIANTS)}
    js = json.dumps(res, indent=1)
    print(js)
    if a.out:
        open(a.out, "w").write(js)


if __name__ == "__main__":
    main()
