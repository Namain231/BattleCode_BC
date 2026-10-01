"""Replay -> per-turn game state, as each dragon could know it on an UNKNOWN map.

Tracks the true board (bodies, pearls, who is alive) from replay events, plus, for every dragon, the memory its
own process would have: terrain it has seen (its 7x7 windows since birth; a split child starts blank) and the
teammates it has seen (id -> last round, visible length, head cell). Top teams' sonar payloads are mostly hashed,
so "heard" teammates are approximated by "seen" ones; see RULE_MINING_SPEC.md.

Usage:
    for turn in turns(path):          # one Turn per dragon-turn, in engine order
        turn.state / turn.action / turn.outcome
"""
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from replay_lite import decode_lite  # noqa: E402

from . import mapgeo  # noqa: E402

KINDS = {"roundStart", "turnStart", "dragonAction", "dragonUpdate", "dragonSplit", "dragonDeath", "tileChange"}
DEATHS = ("wall", "self", "body", "headon", "novalid")
VIEW = 3            # Chebyshev radius of the 7x7 window


@dataclass
class Action:
    act: str = "none"       # move / split / suicide / none
    dirs: str = ""
    size: int = 0


@dataclass
class Outcome:
    died: str = ""          # "" or one of DEATHS
    ate: int = 0            # pearls eaten this turn
    child: int = -1         # id of a split child, -1 if none
    drops: list = field(default_factory=list)   # cells that became pearls when this dragon died


class Game:
    """True state plus per-dragon memories, updated event by event."""

    def __init__(self, map_text, game_id=""):
        self.geo = mapgeo.parse(map_text)
        self.game_id = game_id
        self.team, self.body = {}, {}
        for i, (t, cells) in enumerate(self.geo.dragons):
            self.team[i] = t
            self.body[i] = [self.geo.cell(x, y) for x, y in cells]
        self.alive = set(self.team)
        self.pearl = bytearray(self.geo.n)
        self.round = 0
        self.seen = {i: bytearray(self.geo.n) for i in self.team}     # per-dragon terrain memory
        self.mates = {i: {} for i in self.team}                       # per-dragon: mate id -> (round, vlen, head)
        self.last_eat = {i: 0 for i in self.team}
        self.born = {i: 0 for i in self.team}
        self.prev_head = {}                                           # id -> head cell at its previous turn
        self.prev_len = {}                                            # id -> length at its previous turn
        self.eat_log = []                                             # (round, cell, eater id)
        self.heads_now = {}                                           # id -> {other id: head} seen this turn
        self.heads_prev = {}                                          # id -> the same, from its previous turn

    # ---- queries ---------------------------------------------------------
    def length(self, i):
        return len(self.body[i])

    def head(self, i):
        return self.body[i][0]

    def units(self, team):
        return sum(1 for j in self.alive if self.team[j] == team)

    def in_view(self, i, c):
        return self.geo.cheb(self.head(i), c) <= VIEW

    def visible_len(self, viewer, j):
        """Segments of dragon j inside viewer's window (what the protocol shows)."""
        return sum(1 for c in self.body[j] if self.in_view(viewer, c))

    def visible_heads(self, i):
        """Other living dragons whose head is in i's window: [(id, team, head, visible_len)]."""
        out = []
        for j in self.alive:
            if j != i and self.in_view(i, self.body[j][0]):
                out.append((j, self.team[j], self.body[j][0], self.visible_len(i, j)))
        return out

    def occupied(self):
        occ = {}
        for j in self.alive:
            for k, c in enumerate(self.body[j]):
                occ[c] = (j, k)
        return occ

    def known(self, i):
        s = self.seen[i]
        return lambda c: s[c] == 1

    # ---- memory ------------------------------------------------------------
    def observe(self, i):
        """Update dragon i's memory with its current 7x7 window (called at the start of its turn)."""
        g = self.geo
        # "last ate" as the dragon itself can tell: its length grew since its previous turn (it ate then)
        L = self.length(i)
        if i in self.prev_len and L > self.prev_len[i]:
            self.last_eat[i] = self.round - 1
        self.prev_len[i] = L
        hx, hy = g.xy(self.head(i))
        s = self.seen[i]
        for dy in range(-VIEW, VIEW + 1):
            for dx in range(-VIEW, VIEW + 1):
                s[g.cell(hx + dx, hy + dy)] = 1
        m = self.mates[i]
        vis = self.visible_heads(i)
        for j, t, h, vl in vis:
            if t == self.team[i]:
                m[j] = (self.round, vl, h)
        self.heads_prev[i] = self.heads_now.get(i, {})
        self.heads_now[i] = {j: h for j, t, h, vl in vis}

    # ---- event application -----------------------------------------------------
    def new_dragon(self, j, team, cells):
        self.team[j] = team
        self.body[j] = cells
        self.alive.add(j)
        self.seen[j] = bytearray(self.geo.n)
        self.mates[j] = {}
        self.last_eat[j] = self.round
        self.born[j] = self.round
        self.heads_now[j] = {}


@dataclass
class Turn:
    game: Game
    id: int
    team: int
    round: int
    length: int
    action: Action
    outcome: Outcome
    snapshot: dict          # pre-action facts captured at turnStart (see _snapshot)


def _snapshot(g, i):
    """Everything a feature needs from BEFORE the action, captured cheaply at turnStart."""
    return {
        "head": g.head(i),
        "body": list(g.body[i]),
        "units": g.units(g.team[i]),
        "visible": g.visible_heads(i),
        "mates": dict(g.mates[i]),
        "last_eat": g.last_eat[i],
        "born": g.born[i],
        "prev_head": g.prev_head.get(i, -1),
        "heads_prev": dict(g.heads_prev.get(i, {})),
        "seen_count": g.seen[i].count(1),
        "occ": g.occupied(),
    }


def turns(path, want=None):
    """Yield a Turn for every dragon-turn (or only for dragons where want(game, id) is true).

    The Turn is yielded after its outcome is known (at the next turnStart / end of replay), but its snapshot and
    the game's pearls/bodies-at-yield differ: features must use turn.snapshot for pre-action facts. For
    convenience the pre-action pearl field is also kept in snapshot["pearls"] when want() selects the turn.
    """
    rep = decode_lite(path, KINDS)
    g = Game(rep["map"], os.path.basename(path))
    g.result = rep.get("result")
    cur = None          # Turn being filled
    cleared = set()     # pearls removed since the last body update (the engine logs the eat before the move)

    def close():
        nonlocal cur
        t, cur = cur, None
        return t

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            g.round = e["round"]
            if cur:
                yield close()
        elif k == "turnStart":
            if cur:
                yield close()
            i = e["id"]
            if i not in g.alive:
                continue
            g.observe(i)
            if want is None or want(g, i):
                snap = _snapshot(g, i)
                snap["pearls"] = bytes(g.pearl)
                cur = Turn(g, i, g.team[i], g.round, g.length(i), Action(), Outcome(), snap)
            g.prev_head[i] = g.head(i)
        elif k == "dragonAction":
            if cur and e["id"] == cur.id:
                cur.action = Action(str(e.get("act", "none")), e.get("dirs", "") or "", e.get("size") or 0)
        elif k == "dragonUpdate":
            j, h = e["id"], e.get("head")
            if j not in g.body or h is None:
                continue
            hc, tc = g.geo.cell(*h), g.geo.cell(*e["tail"])
            b = g.body[j]
            if b[0] != hc:
                b.insert(0, hc)
            while len(b) > 1 and b[-1] != tc:
                b.pop()
            if g.pearl[hc] or hc in cleared:
                g.pearl[hc] = 0
                g.eat_log.append((g.round, hc, j))
                if cur and cur.id == j:
                    cur.outcome.ate += 1
            cleared.clear()
        elif k == "tileChange":
            c = g.geo.cell(*e["tile"])
            if not e["pearl"] and g.pearl[c]:
                cleared.add(c)
            g.pearl[c] = 1 if e["pearl"] else 0
            if e["pearl"] and cur and cur.outcome.died:
                cur.outcome.drops.append(c)
        elif k == "dragonSplit":
            g.body[e["parent"]] = [g.geo.cell(x, y) for x, y in e["parentBody"]]
            g.new_dragon(e["child"], e["team"], [g.geo.cell(x, y) for x, y in e["childBody"]])
            if cur and cur.id == e["parent"]:
                cur.outcome.child = e["child"]
        elif k == "dragonDeath":
            j = e["id"]
            g.alive.discard(j)
            if cur and cur.id == j:
                cur.outcome.died = DEATHS[e["reason"]] if e["reason"] < len(DEATHS) else "?"
    if cur:
        yield close()
