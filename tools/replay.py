"""Read .replay files (gzip + Cap'n Proto packed), as written by the judge and `unswbc run`.

The schema is the one the replay viewer carries (see its generated classes).

    python tools/replay.py ladder/305466.replay [--team B] [--deaths] [--summary]
"""
import argparse
import gzip
import struct
import sys

EVENT_KINDS = ["roundStart", "turnStart", "pearlCountdown", "tileChange", "dragonAction", "engineLog",
               "dragonLog", "dragonIndicator", "debugDraw", "dragonUpdate", "dragonSplit", "dragonDeath",
               "sonarPing"]
DEATHS = ["hit wall", "hit self", "hit other body", "head to head", "no valid action"]
DIRS = "NESW"


def unpack(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        tag = data[i]; i += 1
        word = bytearray(8)
        for b in range(8):
            if tag & (1 << b):
                word[b] = data[i]; i += 1
        out += word
        if tag == 0:
            count = data[i]; i += 1
            out += bytes(8 * count)
        elif tag == 0xFF:
            count = data[i]; i += 1
            out += data[i:i + 8 * count]; i += 8 * count
    return bytes(out)


class Msg:
    def __init__(self, raw):
        nseg = struct.unpack_from("<I", raw, 0)[0] + 1
        sizes = struct.unpack_from(f"<{nseg}I", raw, 4)
        off = 4 + 4 * nseg
        off += (8 - off % 8) % 8
        self.segs = []
        for s in sizes:
            self.segs.append(raw[off:off + 8 * s]); off += 8 * s

    def word(self, seg, idx):
        return struct.unpack_from("<Q", self.segs[seg], idx * 8)[0]

    def resolve(self, seg, idx):
        """Follow the pointer at (seg, word idx); returns (seg, pointer word index, pointer value, content start)."""
        p = self.word(seg, idx)
        if p == 0:
            return None
        kind = p & 3
        if kind == 2:  # far pointer
            double = (p >> 2) & 1
            pad = (p >> 3) & ((1 << 29) - 1)
            tseg = p >> 32
            if not double:
                return self.resolve(tseg, pad)
            land = self.word(tseg, pad)
            tag = self.word(tseg, pad + 1)
            cseg = land >> 32
            cstart = (land >> 3) & ((1 << 29) - 1)
            return (cseg, None, tag, cstart)
        offset = (p >> 2) & ((1 << 30) - 1)
        if offset >= 1 << 29:
            offset -= 1 << 30
        return (seg, idx, p, idx + 1 + offset)

    def struct(self, seg, idx):
        r = self.resolve(seg, idx)
        if r is None:
            return None
        s, _, p, start = r
        dw = (p >> 32) & 0xFFFF
        pw = (p >> 48) & 0xFFFF
        return Struct(self, s, start, dw, pw)

    def list(self, seg, idx):
        r = self.resolve(seg, idx)
        if r is None:
            return None
        s, _, p, start = r
        esize = (p >> 32) & 7
        count = p >> 35
        return (s, start, esize, count)


class Struct:
    def __init__(self, msg, seg, start, dw, pw):
        self.m, self.seg, self.start, self.dw, self.pw = msg, seg, start, dw, pw

    def _bytes(self, off, size):
        if off + size > self.dw * 8:
            return bytes(size)
        base = self.start * 8 + off
        return self.m.segs[self.seg][base:base + size]

    def u16(self, off): return struct.unpack("<H", self._bytes(off, 2))[0]
    def i32(self, off): return struct.unpack("<i", self._bytes(off, 4))[0]
    def u32(self, off): return struct.unpack("<I", self._bytes(off, 4))[0]
    def u64(self, off): return struct.unpack("<Q", self._bytes(off, 8))[0]
    def bit(self, n): return (self._bytes(n // 8, 1)[0] >> (n % 8)) & 1

    def ptr(self, i):
        return (self.seg, self.start + self.dw + i) if i < self.pw else None

    def struct(self, i):
        p = self.ptr(i)
        return self.m.struct(*p) if p else None

    def text(self, i):
        p = self.ptr(i)
        lst = self.m.list(*p) if p else None
        if not lst:
            return ""
        s, start, _, count = lst
        return self.m.segs[s][start * 8:start * 8 + count].rstrip(b"\0").decode("utf-8", "replace")

    def structs(self, i):
        p = self.ptr(i)
        lst = self.m.list(*p) if p else None
        if not lst:
            return []
        s, start, esize, count = lst
        if esize != 7:
            return []
        tag = self.m.word(s, start)
        n = (tag >> 2) & ((1 << 30) - 1)
        dw = (tag >> 32) & 0xFFFF
        pw = (tag >> 48) & 0xFFFF
        return [Struct(self.m, s, start + 1 + k * (dw + pw), dw, pw) for k in range(n)]


def point(st):
    return (st.i32(0), st.i32(4)) if st else None


def load(path):
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    msg = Msg(unpack(raw))
    root = msg.struct(0, 0)
    rep = {"map": root.text(0), "botA": root.text(1), "botB": root.text(2), "events": []}
    for ev in root.structs(3):
        which = ev.u16(0)
        kind = EVENT_KINDS[which] if which < len(EVENT_KINDS) else f"?{which}"
        body = ev.struct(0)
        e = {"kind": kind}
        if body is None:
            rep["events"].append(e); continue
        if kind == "roundStart":
            e["round"] = body.i32(0)
        elif kind == "turnStart":
            e["id"] = body.i32(0)
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
        rep["events"].append(e)
    res = root.struct(4)
    if res:
        teams = []
        for i in (0, 1):
            t = res.struct(i)
            teams.append({"count": t.i32(0), "longest": t.i32(4), "total": t.i32(8)} if t else None)
        rep["result"] = {"endReason": res.u16(2), "winner": res.u16(6) if res.u16(4) else None, "A": teams[0], "B": teams[1]}
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--team", help="which team letter is ours (for filtering)")
    ap.add_argument("--deaths", action="store_true")
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()
    rep = load(args.path)
    print(f"map: {rep['map'].splitlines()[0] if rep['map'] else '?'}  A={rep['botA']}  B={rep['botB']}  result={rep.get('result')}")
    if args.dump:
        for e in rep["events"][:300]:
            print(e)


if __name__ == "__main__":
    main()
