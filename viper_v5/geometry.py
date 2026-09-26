"""
Toroidal Grid Geometry for viper_v5 Apex.
"""
from typing import Tuple, List
from helper import Direction, Position


def torus_delta(c1: int, c2: int, size: int) -> int:
    """Signed shortest distance along a toroidal axis."""
    diff = (c2 - c1) % size
    if diff > size // 2:
        diff -= size
    return diff


def torus_manhattan_dist(p1: Position, p2: Position, width: int, height: int) -> int:
    """Manhattan distance on a torus."""
    dx = abs(torus_delta(p1.x, p2.x, width))
    dy = abs(torus_delta(p1.y, p2.y, height))
    return dx + dy


def step_pos(pos: Position, direction: Direction, width: int, height: int) -> Position:
    """Advance pos by direction with toroidal wrapping."""
    dx, dy = direction.get_offset()
    return Position((pos.x + dx) % width, (pos.y + dy) % height)


def best_directions_toward(src: Position, dst: Position, width: int, height: int) -> List[Direction]:
    """
    Returns directions ordered by how well they close distance toward dst on a torus.
    Primary axis first, then secondary axis, then others.
    """
    dx = torus_delta(src.x, dst.x, width)
    dy = torus_delta(src.y, dst.y, height)

    dirs_with_score = []
    for d in Direction.get_direction_list():
        ox, oy = d.get_offset()
        # Dot product with desired delta
        score = ox * dx + oy * dy
        dirs_with_score.append((score, d))

    dirs_with_score.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in dirs_with_score]
