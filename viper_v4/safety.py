"""
Safety and Graph Connectivity Engine for viper_v4.
Features:
- Dynamic tail-vacancy simulation (tail vacates if no pearl eaten)
- Tail-chasing loop reachability
- Compactness / wall-hugging edge counting
- Hazard mapping
"""
from collections import deque
from typing import Tuple, List, Set, Optional
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos

def is_immediate_collision(ct: Controller, game: Game, direction: Direction) -> Tuple[bool, str]:
    """Checks if moving in direction from current head results in instant death."""
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
    """Returns (enemy_hazards, friendly_hazards)."""
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
                    nb_key = (nb.x, nb.y)
                    if is_friendly:
                        friendly_hazards.add(nb_key)
                    else:
                        enemy_hazards.add(nb_key)

    return enemy_hazards, friendly_hazards

def find_my_tail(ct: Controller) -> Optional[Position]:
    """Finds our dragon's current tail segment."""
    my_id = ct.get_id()
    head_pos = ct.get_position()
    my_parts = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.get_id() == my_id and not part.is_head():
            my_parts.append(part.get_position())

    if not my_parts:
        return None

    # Sort by Manhattan distance from head descending (furthest non-head is the tail)
    my_parts.sort(key=lambda p: abs(p.x - head_pos.x) + abs(p.y - head_pos.y), reverse=True)
    return my_parts[0]

def compute_chamber_and_tail_loop(ct: Controller, game: Game, next_pos: Position,
                                  my_len: int, max_depth: int = 50) -> Tuple[int, bool]:
    """
    Simulates space after stepping onto next_pos.
    If next_pos has NO pearl, the dragon's current tail will vacate its cell!
    Checks if a path to the retreating tail exists (guaranteed loop survival).
    Returns (reachable_count, can_reach_tail).
    """
    dest_tile = ct.get_tile(next_pos)
    has_pearl = dest_tile is not None and (dest_tile.has_pearl() or dest_tile.get_pearl_time() == 0)

    tail_pos = find_my_tail(ct)
    vacated_tail_key = None
    if not has_pearl and tail_pos is not None:
        # Tail vacates!
        vacated_tail_key = (tail_pos.x, tail_pos.y)

    visited: Set[Tuple[int, int]] = set()
    visited.add((next_pos.x, next_pos.y))
    queue = deque([next_pos])

    can_reach_tail = False
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

            nb = step_pos(curr, d, game.width, game.height)
            nb_key = (nb.x, nb.y)
            if nb_key in visited:
                continue

            if vacated_tail_key is not None and nb_key == vacated_tail_key:
                # Reached retreating tail! Infinite loop path confirmed!
                can_reach_tail = True
                visited.add(nb_key)
                queue.append(nb)
                continue

            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                continue

            visited.add(nb_key)
            queue.append(nb)

    return count, can_reach_tail

def count_compactness(ct: Controller, game: Game, pos: Position) -> int:
    """
    Wall-hugging / compactness metric: counts adjacent obstacles
    (kelp or dragon body segments) around pos.
    Hugging boundaries leaves the center unfragmented.
    """
    tile = ct.get_tile(pos)
    if tile is None:
        return 0

    adjacent_walls = 0
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if edge.get_edge_type() == EdgeType.KELP:
            adjacent_walls += 1
        else:
            nb = step_pos(pos, d, game.width, game.height)
            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                adjacent_walls += 1

    return adjacent_walls
