"""
Toroidal Grid Geometry for viper_v4.
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

def torus_chebyshev_dist(p1: Position, p2: Position, width: int, height: int) -> int:
    """Chebyshev distance on a torus."""
    dx = abs(torus_delta(p1.x, p2.x, width))
    dy = abs(torus_delta(p1.y, p2.y, height))
    return max(dx, dy)

def step_pos(pos: Position, direction: Direction, width: int, height: int) -> Position:
    """Advance pos by direction with toroidal wrapping."""
    dx, dy = direction.get_offset()
    return Position((pos.x + dx) % width, (pos.y + dy) % height)

def get_neighbors(pos: Position, width: int, height: int) -> List[Tuple[Direction, Position]]:
    """Returns list of (Direction, Position) for all 4 cardinal neighbors."""
    res = []
    for d in Direction.get_direction_list():
        res.append((d, step_pos(pos, d, width, height)))
    return res
