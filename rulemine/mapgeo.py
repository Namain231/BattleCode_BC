"""Map geometry from a .map text: wrap, kelp and portal steps, and which edges a dragon can know.

Edge convention (docs/map-files.md): rows of horizontal edges (a tile row's north side) alternate with rows of
vertical edges (a tile's west side), each row width + 1 long. Portals are teleports: crossing a portal edge exits
the partner edge in the same direction (as the engine and the Abyss framework do). An unpaired portal end is a wall.
"""
from dataclasses import dataclass, field

DIRS = "NESW"
DX = (0, 1, 0, -1)
DY = (-1, 0, 1, 0)


@dataclass
class Geo:
    w: int
    h: int
    kelp_n: list            # kelp_n[c]: the north side of tile c is kelp
    kelp_w: list            # kelp_w[c]: the west side of tile c is kelp
    portal: dict            # (c, 'N'|'W') -> (partner cell, 'N'|'W')
    name: str = ""
    dragons: list = field(default_factory=list)   # [(team, [(x, y), ...]), ...] in id order

    @property
    def n(self):
        return self.w * self.h

    def cell(self, x, y):
        return (y % self.h) * self.w + (x % self.w)

    def xy(self, c):
        return c % self.w, c // self.w

    def edge(self, c, d):
        """(owner cell, 'N'|'W') of the edge on side d of tile c."""
        x, y = self.xy(c)
        if d == 0:
            return c, "N"
        if d == 2:
            return self.cell(x, y + 1), "N"
        if d == 3:
            return c, "W"
        return self.cell(x + 1, y), "W"

    def edge_cells(self, c, d):
        """The two tiles an edge separates (for knowledge: an edge is seen when either tile is seen)."""
        x, y = self.xy(c)
        return c, self.cell(x + DX[d], y + DY[d])

    def step(self, c, d, known=None):
        """Tile reached by stepping d from c, or -1 if blocked.

        known: optional callable cell -> bool. Unknown edges are treated as open (the bot's optimistic
        assumption); a portal is followed only when both of its ends are known, else it is a wall.
        """
        oc, o = self.edge(c, d)
        a, b = self.edge_cells(c, d)
        edge_known = known is None or known(a) or known(b)
        if (oc, o) in self.portal:
            if not edge_known:
                return self._plain(c, d)
            pc, _ = self.portal[(oc, o)]
            px, py = self.xy(pc)
            other = self.cell(px, py - 1) if o == "N" else self.cell(px - 1, py)
            if known is not None and not (known(pc) or known(other)):   # partner edge never in view
                return -1
            if o == "N":
                return self.cell(px, py if d == 2 else py - 1)
            return self.cell(px if d == 1 else px - 1, py)
        if edge_known and (self.kelp_n[oc] if o == "N" else self.kelp_w[oc]):
            return -1
        return self._plain(c, d)

    def _plain(self, c, d):
        x, y = self.xy(c)
        return self.cell(x + DX[d], y + DY[d])

    def torus_manhattan(self, a, b):
        ax, ay = self.xy(a)
        bx, by = self.xy(b)
        dx, dy = abs(ax - bx), abs(ay - by)
        return min(dx, self.w - dx) + min(dy, self.h - dy)

    def cheb(self, a, b):
        ax, ay = self.xy(a)
        bx, by = self.xy(b)
        dx, dy = abs(ax - bx), abs(ay - by)
        return max(min(dx, self.w - dx), min(dy, self.h - dy))


def parse(text):
    w = h = 0
    name = ""
    edges, dragons = [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "MAP":
            w, h = int(p[1]), int(p[2])
        elif p[0] == "MAP_NAME":
            name = " ".join(p[1:])
        elif p[0] == "EDGE":
            edges.append((int(p[1]), int(p[2]), int(p[3]) if len(p) > 3 else -1))
        elif p[0] == "DRAGON":
            team, k = int(p[1]), int(p[2])
            c = [int(v) for v in p[3:3 + 2 * k]]
            dragons.append((team, [(c[2 * i], c[2 * i + 1]) for i in range(k)]))
    kelp_n = [False] * (w * h)
    kelp_w = [False] * (w * h)
    by_pid = {}
    for index, kind, pid in edges:
        if kind == 0:
            continue
        r, col = divmod(index, w + 1)
        if r % 2 == 0:
            x, y, o = col % w, (r // 2) % h, "N"
        else:
            x, y, o = col % w, ((r - 1) // 2) % h, "W"
        c = y * w + x
        if kind == 1:
            (kelp_n if o == "N" else kelp_w)[c] = True
        elif kind == 2:
            by_pid.setdefault(pid, []).append((c, o))
    portal = {}
    for ends in by_pid.values():
        if len(ends) == 2 and ends[0][1] == ends[1][1]:
            portal[ends[0]] = ends[1]
            portal[ends[1]] = ends[0]
        else:   # unpaired or mismatched: a wall
            for c, o in ends:
                (kelp_n if o == "N" else kelp_w)[c] = True
    return Geo(w, h, kelp_n, kelp_w, portal, name, dragons)
