from conftest import MAPS
from rulemine import mapgeo


def geo(name):
    return mapgeo.parse((MAPS / f"{name}.map").read_text())


def test_portals_dead_end_pocket_has_one_exit():
    g = geo("portals")
    c = g.cell(16, 7)   # a known one-tile pocket (kelp N, E, S)
    assert [g.step(c, d) for d in range(4)].count(-1) == 3
    assert g.step(c, 3) == g.cell(15, 7)


def test_every_portal_crossing_is_reversible():
    for name in ("portals", "default", "autarky", "trauma", "dilemma"):
        g = geo(name)
        assert g.portal, name
        for (c, o), _ in g.portal.items():
            dirs = (0, 2) if o == "N" else (1, 3)
            for d in dirs:
                # the tile on the other side of this edge, stepping through it
                start = c if d in (0, 3) else (g.cell(g.xy(c)[0], g.xy(c)[1] - 1) if o == "N" else g.cell(g.xy(c)[0] - 1, g.xy(c)[1]))
                n = g.step(start, d)
                assert n >= 0
                assert g.step(n, d ^ 2) == start, (name, c, o, d)


def test_unknown_edges_are_open_and_unknown_portals_are_walls():
    g = geo("portals")
    c = g.cell(16, 7)
    nothing = lambda cell: False
    assert all(g.step(c, d, known=nothing) >= 0 for d in range(4))   # kelp not yet seen
    (pc, o), _ = next(iter(g.portal.items()))
    d = 0 if o == "N" else 3
    only_here = lambda cell: cell == pc
    assert g.step(pc, d, known=only_here) == -1                   # partner end unseen
