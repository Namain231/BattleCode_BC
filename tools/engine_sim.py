"""In-memory Loong rules, post 2026-10-01 (no sonar or bot execution).

Bodies are head-first lists of (x, y). State.round is the LAST completed
zero-based round (-1 initially). step clones mutable state, ticks pearls,
then executes IDs in order, including newborns. Actions may be a mapping
id -> replay action dictionary, or a callable(state, id) for rollouts.
This is sequential execution, as the engine requires, not simultaneous.

Sources: docs/execution-order.md and Loong's MIT CPU reference engine.h.
The reference predates the free-step/queen changes; those follow current docs.
SpawnInput supplies replay pearl spawns and countdown resets WITHOUT applying
any movement/death outputs. With a seed, the mt19937_64 port also allows fully
deterministic standalone spawning. Maps are immutable and shared by branches.

Portions derived from Loong's engine.h, originally:
Copyright (c) 2026 UNSW CPMSoc, MIT License.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from dataclasses import dataclass, field
from typing import Mapping

DIRS = "NESW"
DEATHS = ("hit wall", "hit self", "hit other body", "head to head", "no valid action")
MASK64 = (1 << 64) - 1


class Rng:
    """libc++ mt19937_64, with the reference's modulo gap draw."""
    def __init__(self, seed):
        self.words = [seed & MASK64]
        for i in range(1, 312):
            v = self.words[-1]
            self.words.append((6364136223846793005 * (v ^ (v >> 62)) + i) & MASK64)
        self.index = 0

    def copy(self):
        result = object.__new__(Rng)
        result.words, result.index = self.words.copy(), self.index
        return result

    def draw(self):
        i = self.index
        j = (i + 1) % 312
        y = (self.words[i] & 0xFFFFFFFF80000000) | (self.words[j] & 0x7FFFFFFF)
        z = self.words[(i + 156) % 312] ^ (y >> 1) ^ (0xB5026F5AA96619E9 if y & 1 else 0)
        self.words[i] = z
        self.index = j
        z ^= (z >> 29) & 0x5555555555555555
        z ^= (z << 17) & 0x71D67FFFEDA60000
        z ^= (z << 37) & 0xFFF7EEE000000000
        return (z ^ (z >> 43)) & MASK64


@dataclass(frozen=True)
class Board:
    width: int
    height: int
    neighbours: Mapping  # (point, direction) -> point, or None for kelp
    gaps: Mapping        # point -> (min_gap, max_gap), includes disabled tiles
    symmetry: str = "none"
    unit_limit: int = 64

    def mirror(self, p):
        x, y = p
        if self.symmetry in ("y", "xy"):
            x = self.width - 1 - x
        if self.symmetry in ("x", "xy"):
            y = self.height - 1 - y
        return x, y

    def facing(self, neck, head):
        return next((d for d in range(4) if self.neighbours[neck, d] == head), -1)


@dataclass
class Dragon:
    id: int
    team: int
    body: list
    facing: int
    alive: bool = True
    death: int | None = None


@dataclass
class SpawnInput:
    """Only round-start events; never include eats or death drops here."""
    pearls: set = field(default_factory=set)
    countdowns: dict = field(default_factory=dict)


@dataclass
class State:
    board: Board
    dragons: dict
    pearls: set
    countdowns: dict
    rng: Rng
    round: int = -1
    next_id: int = 0
    over: bool = False
    winner: int | None = None
    events: list = field(default_factory=list)

    def copy(self):
        return State(self.board, {i: Dragon(d.id, d.team, d.body.copy(), d.facing,
                                           d.alive, d.death) for i, d in self.dragons.items()},
                     self.pearls.copy(), self.countdowns.copy(), self.rng.copy(),
                     self.round, self.next_id, self.over, self.winner)


def load_map(text, seed=1):
    """Load official map text. Boundary edges alias the wrapped edge."""
    from types import MappingProxyType
    lines = [line.split() for line in text.splitlines() if line.split()]
    w, h = next((int(p[1]), int(p[2])) for p in lines if p[0] == "MAP")
    edges = {(o, x, y): (0, -1) for o in (0, 1) for y in range(h) for x in range(w)}
    gaps = {(x, y): (0, 0) for y in range(h) for x in range(w)}
    starts, symmetry, limit = [], "none", 64
    for p in lines:
        if p[0] == "SYMMETRY":
            symmetry = p[1].lower()
        elif p[0] == "UNIT_LIMIT":
            limit = int(p[1])
        elif p[0] == "TILE":
            x, y, lo, hi = map(int, p[1:5])
            gaps[x, y] = lo, hi
        elif p[0] == "EDGE":
            index, kind, portal = map(int, p[1:4])
            row, col = divmod(index, w + 1)
            edges[row % 2, col % w, (row // 2) % h] = kind, portal
        elif p[0] == "DRAGON":
            team, length = int(p[1]), int(p[2])
            starts.append((team, [(int(p[3 + 2*i]), int(p[4 + 2*i])) for i in range(length)]))
    portals = {}
    for edge, (kind, pid) in edges.items():
        if kind == 2:
            portals.setdefault(pid, []).append(edge)
    for pid, pair in portals.items():
        if len(pair) != 2 or pair[0][0] != pair[1][0]:
            raise ValueError(f"Invalid portal {pid}: {pair}")
    neighbours = {}
    for y in range(h):
        for x in range(w):
            for d, (dx, dy) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
                edge = ((0, x, y), (1, (x+1) % w, y),
                        (0, x, (y+1) % h), (1, x, y))[d]
                kind, pid = edges[edge]
                dest = ((x+dx) % w, (y+dy) % h)
                if kind == 1:
                    dest = None
                elif kind == 2:
                    a, b = portals[pid]
                    o, px, py = b if a == edge else a
                    dest = (px, (py - (d == 0)) % h) if o == 0 else ((px - (d == 3)) % w, py)
                neighbours[(x, y), d] = dest
    board = Board(w, h, MappingProxyType(neighbours), MappingProxyType(gaps), symmetry, limit)
    dragons = {i: Dragon(i, team, body, board.facing(body[1], body[0]))
               for i, (team, body) in enumerate(starts)}
    state = State(board, dragons, set(), {p: -1 for p in gaps}, Rng(seed), next_id=len(dragons))
    for p, (lo, hi) in gaps.items():
        mirror = board.mirror(p)
        if (mirror[1], mirror[0]) < (p[1], p[0]) or hi == 0:
            continue
        state.countdowns[p] = state.countdowns[mirror] = lo + state.rng.draw() % (hi-lo+1)
    return state


def _tile(state, p, pearl):
    if pearl:
        state.pearls.add(p)
    else:
        state.pearls.discard(p)
    state.events.append({"kind": "tileChange", "tile": p, "pearl": bool(pearl)})


def _kill(state, dragon, reason, occupancy):
    dragon.alive, dragon.death = False, reason
    state.events.append({"kind": "dragonDeath", "id": dragon.id, "reason": reason})
    for p in dragon.body[::2]:
        _tile(state, p, True)
    for p in dragon.body:
        occupancy.pop(p, None)


def _tick(state, occupancy, spawn_input):
    # Replay resets/spawns are exogenous; ordinary countdown decreases are ours.
    for p, (lo, hi) in state.board.gaps.items():
        mirror = state.board.mirror(p)
        if (mirror[1], mirror[0]) < (p[1], p[0]) or hi == 0:
            continue
        remaining = state.countdowns[p] - 1
        state.countdowns[p] = state.countdowns[mirror] = remaining
        if remaining > 0 or spawn_input is not None:
            continue
        for q in dict.fromkeys((p, mirror)):
            if q not in state.pearls and q not in occupancy:
                _tile(state, q, True)
        gap = lo + state.rng.draw() % (hi-lo+1)
        state.countdowns[p] = state.countdowns[mirror] = gap
    if spawn_input is not None:
        for p in spawn_input.pearls:
            if p in occupancy or p in state.pearls:
                raise ValueError(f"Impossible replay spawn at {p}")
            state.pearls.add(p)
        state.countdowns.update(spawn_input.countdowns)


def apply_action(state, dragon_id, action, occupancy=None):
    """Mutating single turn primitive; step is the branching/copying API.

    Returns child ID or None. Output events expose each individual move, so
    the oracle verifies intermediate sprint bodies rather than just endpoints.
    """
    d = state.dragons[dragon_id]
    if not d.alive:
        return None
    if occupancy is None:
        occupancy = {p: i for i, other in state.dragons.items() if other.alive for p in other.body}
    action = action or {}
    kind = action.get("act", "suicide")
    if kind == "split":
        size = action.get("size", 0)
        if not isinstance(size, int) or size < 2 or len(d.body)-size < 2 or sum(
                x.alive and x.team == d.team for x in state.dragons.values()) >= state.board.unit_limit:
            _kill(state, d, 4, occupancy)
            return None
        body = list(reversed(d.body[-size:]))
        del d.body[-size:]
        child = Dragon(state.next_id, d.team, body, state.board.facing(body[1], body[0]))
        state.next_id += 1
        state.dragons[child.id] = child
        for p in body:
            occupancy[p] = child.id
        state.events.append({"kind": "dragonSplit", "parent": d.id, "child": child.id,
                             "team": d.team, "parentBody": d.body.copy(), "childBody": body.copy()})
        return child.id
    dirs = action.get("dirs", "") if kind == "move" else ""
    if not dirs or any(direction not in DIRS for direction in dirs):
        _kill(state, d, 4, occupancy)
        return None
    free_steps = (len(d.body)+3)//4
    for j, direction in enumerate(dirs):
        pay = j >= free_steps
        if pay and len(d.body) <= 2:
            _kill(state, d, 4, occupancy)
            break
        d.facing = DIRS.index(direction)
        dest = state.board.neighbours[d.body[0], d.facing]
        other_id = occupancy.get(dest)
        if dest is None:
            _kill(state, d, 0, occupancy)
            break
        if other_id == d.id:
            _kill(state, d, 1, occupancy)
            break
        if other_id is not None:
            other = state.dragons[other_id]
            reason = 3 if other.body[0] == dest else 2
            if reason == 3:
                _kill(state, other, 3, occupancy)
            _kill(state, d, reason, occupancy)
            break
        d.body.insert(0, dest)
        occupancy[dest] = d.id
        if dest in state.pearls:
            _tile(state, dest, False)
        else:
            occupancy.pop(d.body.pop())
        if pay:
            occupancy.pop(d.body.pop())
        state.events.append({"kind": "dragonUpdate", "id": d.id, "facing": d.facing,
                             "head": d.body[0], "tail": d.body[-1]})
    return None


def standings(state):
    scores = []
    for team in (0, 1):
        lengths = [len(d.body) for d in state.dragons.values() if d.alive and d.team == team]
        queen = state.dragons.get(team)
        scores.append((len(queen.body) if queen and queen.alive and queen.team == team else 0,
                       max(lengths, default=0), sum(lengths)))
    return scores


def step(state, actions, spawn_input=None):
    """Return a new state after ONE round. Missing actions mean suicide.

    Newborn IDs must have actions too; callable policies can decide from their
    actual post-split state. Terminal states cannot be advanced accidentally.
    """
    if state.over:
        raise ValueError("Cannot advance a terminal state")
    result = state.copy()
    result.round += 1
    occupancy = {p: i for i, d in result.dragons.items() if d.alive for p in d.body}
    _tick(result, occupancy, spawn_input)
    queue = sorted(i for i, d in result.dragons.items() if d.alive)
    cursor = 0
    while cursor < len(queue):
        i = queue[cursor]
        cursor += 1
        if not result.dragons[i].alive:
            continue
        action = actions(result, i) if callable(actions) else actions.get(i)
        child = apply_action(result, i, action, occupancy)
        if child is not None:
            queue.append(child)
    scores = standings(result)
    eliminated = [not any(d.alive and d.team == t for d in result.dragons.values()) for t in (0, 1)]
    result.over = any(eliminated) or result.round >= 499
    if any(eliminated):
        result.winner = None if all(eliminated) else (1 if eliminated[0] else 0)
    elif result.over:
        result.winner = 0 if scores[0] > scores[1] else 1 if scores[1] > scores[0] else None
    return result
