"""
Safety Engine for viper_v2.
Handles single-step collision validation, flood-fill chamber sizing,
and head hazard mapping.
"""
from collections import deque
from typing import Tuple, List, Set
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos

def is_immediate_collision(ct: Controller, game: Game, direction: Direction) -> Tuple[bool, str]:
    """Checks if moving in direction results in an instant collision."""
    here = ct.get_position()
    tile = ct.get_tile(here)
    if tile is None:
        return True, "outside_vision"

    edge = tile.get_edge(direction)
    if edge.get_edge_type() == EdgeType.KELP:
        return True, "hit_kelp"

    if edge.get_edge_type() == EdgeType.PORTAL:
        return True, "unknown_portal"

    ahead_pos = step_pos(here, direction, game.width, game.height)
    ahead_tile = ct.get_tile(ahead_pos)
    if ahead_tile is None:
        return False, "unseen"

    part = ahead_tile.get_dragon()
    if part is not None:
        if part.is_head():
            return True, "head_on"
        return True, "hit_body"

    return False, "safe"

def get_head_hazards(ct: Controller, game: Game) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
    """
    Returns (enemy_hazards, friendly_hazards) representing squares
    adjacent to other dragon heads.
    """
    enemy_hazards = set()
    friendly_hazards = set()
    my_team = ct.get_team()
    my_id = ct.get_id()

    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head():
            pos = part.get_position()
            part_id = part.get_id()
            if part_id == my_id:
                continue

            is_friendly = (part.get_team() == my_team)
            for d in Direction.get_direction_list():
                edge = tile.get_edge(d)
                if edge.get_edge_type() == EdgeType.EMPTY:
                    nb = step_pos(pos, d, game.width, game.height)
                    if is_friendly:
                        friendly_hazards.add((nb.x, nb.y))
                    else:
                        enemy_hazards.add((nb.x, nb.y))

    return enemy_hazards, friendly_hazards

def compute_flood_fill(ct: Controller, game: Game, start_pos: Position,
                       max_depth: int = 50) -> int:
    """Calculates accessible chamber size via BFS."""
    visited = set()
    visited.add((start_pos.x, start_pos.y))
    queue = deque([start_pos])

    count = 0
    while queue and count < max_depth:
        curr = queue.popleft()
        count += 1

        curr_tile = ct.get_tile(curr)
        if curr_tile is None:
            continue

        for d in Direction.get_direction_list():
            edge = curr_tile.get_edge(d)
            if edge.get_edge_type() != EdgeType.EMPTY:
                continue

            nb_pos = step_pos(curr, d, game.width, game.height)
            nb_key = (nb_pos.x, nb_pos.y)
            if nb_key in visited:
                continue

            nb_tile = ct.get_tile(nb_pos)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                continue

            visited.add(nb_key)
            queue.append(nb_pos)

    return count
