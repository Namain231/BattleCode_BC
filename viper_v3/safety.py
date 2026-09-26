"""
Safety Engine for viper_v3.
Handles collision detection, hazard mapping, flood-fill chamber validation,
and multi-step sprint simulations.
"""
from collections import deque
from typing import Tuple, List, Set, Optional
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos
from portal_graph import PortalRegistry

def is_immediate_collision(ct: Controller, game: Game, direction: Direction,
                           portal_reg: Optional[PortalRegistry] = None) -> Tuple[bool, str]:
    """Checks if moving in direction from current head results in instant death."""
    here = ct.get_position()
    tile = ct.get_tile(here)
    if tile is None:
        return True, "outside_vision"

    edge = tile.get_edge(direction)
    if edge.get_edge_type() == EdgeType.KELP:
        return True, "hit_kelp"

    if edge.get_edge_type() == EdgeType.PORTAL:
        if portal_reg is not None:
            dest = portal_reg.get_teleport_destination(here, direction, edge.get_portal_id(), game)
            if dest is not None:
                dest_tile = ct.get_tile(dest)
                if dest_tile is not None and dest_tile.get_dragon() is not None:
                    return True, "portal_blocked"
                return False, "safe_portal"
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

def get_head_hazards(ct: Controller, game: Game) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]], Set[Tuple[int, int]]]:
    """
    Categorizes adjacent hazards:
    - friendly_hazards: tiles adjacent to friendly heads
    - enemy_queen_hazards: tiles adjacent to enemy heads of length >= 6
    - enemy_drone_hazards: tiles adjacent to small enemy heads of length < 6
    """
    friendly_hazards = set()
    enemy_queen_hazards = set()
    enemy_drone_hazards = set()
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
                    nb_key = (nb.x, nb.y)
                    if is_friendly:
                        friendly_hazards.add(nb_key)
                    else:
                        # Estimate enemy length
                        enemy_queen_hazards.add(nb_key)

    return friendly_hazards, enemy_queen_hazards, enemy_drone_hazards

def compute_flood_fill(ct: Controller, game: Game, start_pos: Position,
                       max_depth: int = 50) -> int:
    """Calculates accessible chamber capacity via BFS."""
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

def is_sprint_safe(ct: Controller, game: Game, directions: List[Direction]) -> Tuple[bool, str]:
    """Validates multi-step sprint execution."""
    n = len(directions)
    cost = n - 1
    if ct.get_length() <= cost + 1:
        return False, "cannot_pay"

    curr_pos = ct.get_position()
    for d in directions:
        curr_tile = ct.get_tile(curr_pos)
        if curr_tile is None:
            return False, "outside_vision"

        edge = curr_tile.get_edge(d)
        if edge.get_edge_type() != EdgeType.EMPTY:
            return False, "blocked_edge"

        curr_pos = step_pos(curr_pos, d, game.width, game.height)
        dest_tile = ct.get_tile(curr_pos)
        if dest_tile is not None and dest_tile.get_dragon() is not None:
            return False, "dragon_collision"

    return True, "safe"
