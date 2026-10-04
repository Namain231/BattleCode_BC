"""Low-memory replay decode: keep only the event kinds asked for, no pickle cache."""
import struct
from replay import Msg, unpack, point, EVENT_KINDS, DIRS
import gzip

def decode_lite(path, kinds):
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    msg = Msg(unpack(raw))
    root = msg.struct(0, 0)
    rep = {"map": root.text(0), "botA": root.text(1), "botB": root.text(2), "events": []}
    for ev in root.structs(3):
        which = ev.u16(0)
        kind = EVENT_KINDS[which] if which < len(EVENT_KINDS) else f"?{which}"
        if kind not in kinds:
            continue
        body = ev.struct(0)
        e = {"kind": kind}
        if body is None:
            rep["events"].append(e); continue
        if kind == "roundStart":
            e["round"] = body.i32(0)
        elif kind == "turnStart":
            e["id"] = body.i32(0)
        elif kind == "pearlCountdown":
            e["tile"] = point(body.struct(0)); e["countdown"] = body.i32(0)
        elif kind in ("dragonIndicator", "dragonLog", "engineLog"):
            e["id"] = body.i32(0); e["text"] = body.text(0)
        elif kind == "dragonUpdate":
            e["id"] = body.i32(0); e["facing"] = body.u16(4)
            e["head"] = point(body.struct(0)); e["tail"] = point(body.struct(1))
        elif kind == "dragonSplit":
            e["parent"] = body.i32(0); e["child"] = body.i32(4); e["team"] = body.u16(8)
            e["parentBody"] = [point(p) for p in body.structs(0)]
            e["childBody"] = [point(p) for p in body.structs(1)]
        elif kind == "dragonDeath":
            e["id"] = body.i32(0); e["reason"] = body.u16(4)
        elif kind == "dragonAction":
            e["id"] = body.i32(0)
            act = body.struct(0)
            if act:
                w = act.u16(0)
                e["act"] = ["move", "split", "suicide"][w] if w < 3 else w
                if w == 0:
                    lst = act.m.list(*act.ptr(0)) if act.ptr(0) else None
                    if lst:
                        s, start, esize, count = lst
                        raw16 = act.m.segs[s][start * 8:start * 8 + 2 * count]
                        e["dirs"] = "".join(DIRS[struct.unpack_from("<H", raw16, 2 * k)[0] % 4] for k in range(count))
                elif w == 1:
                    e["size"] = act.u32(4) if act.dw else None
            ins = body.struct(1)
            if ins:
                e["points"] = ins.u64(0)
        elif kind == "tileChange":
            e["tile"] = point(body.struct(0)); e["pearl"] = body.bit(0)
        elif kind == "sonarPing":
            # EventSonarPing (replay viewer schema): the full message and what the ray stopped on
            e["sender"] = body.i32(0); e["dir"] = DIRS[body.u16(4) % 4]
            e["hit"] = body.i32(12) if body.u16(6) == 1 else None
            e["value"] = body.u64(16)
            e["hitKind"] = ["unknown", "empty", "kelp", "ally", "ally_head", "enemy", "enemy_head"][min(6, body.u16(24))]
            e["origin"] = point(body.struct(0)); e["end"] = point(body.struct(1))
        rep["events"].append(e)
    res = root.struct(4)
    if res:
        teams = []
        for i in (0, 1):
            t = res.struct(i)
            teams.append({"count": t.i32(0), "longest": t.i32(4), "total": t.i32(8)} if t else None)
        rep["result"] = {"endReason": res.u16(2), "winner": res.u16(6) if res.u16(4) else None, "A": teams[0], "B": teams[1]}
    return rep

