"""
Spatial Voronoi Analysis and Tail Reachability Engine.
Calculates territory control, uncontested pearl count, and tail-chase survival paths.
"""
from collections import deque
from typing import Dict, Set, Tuple, List, Optional
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos

def find_tail_position(ct: Controller) -> Optional[Position]:
    """Finds our dragon's current tail segment in vision if available."""
    my_id = ct.get_id()
    my_parts = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.get_id() == my_id:
            my_parts.append(part)

    if not my_parts:
        return None

    # The tail is a non-head part that no other body part faces into
    head_pos = ct.get_position()
    tails = [p for p in my_parts if not p.is_head()]
    if not tails:
        return None

    # Sort by furthest from head
    tails.sort(key=lambda p: abs(p.get_position().x - head_pos.x) + abs(p.get_position().y - head_pos.y), reverse=True)
    return tails[0].get_position()

def evaluate_voronoi_and_tail(ct: Controller, game: Game, candidate_pos: Position,
                              max_nodes: int = 40) -> Tuple[int, int, bool]:
    """
    Computes:
    - territory_score: reachable cells where we arrive before/equal to enemy
    - controlled_pearls: pearls within our controlled territory
    - can_reach_tail: whether a path to our tail exists
    """
    my_team = ct.get_team()
    enemy_heads = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != my_team:
            enemy_heads.append(part.get_position())

    # BFS from candidate_pos
    my_dist: Dict[Tuple[int, int], int] = {}
    queue = deque([(candidate_pos, 0)])
    my_dist[(candidate_pos.x, candidate_pos.y)] = 0

    while queue and len(my_dist) < max_nodes:
        curr, d = queue.popleft()
        curr_tile = ct.get_tile(curr)
        if curr_tile is None:
            continue

        for direction in Direction.get_direction_list():
            edge = curr_tile.get_edge(direction)
            if edge.get_edge_type() != EdgeType.EMPTY:
                continue

            nb = step_pos(curr, direction, game.width, game.height)
            nb_key = (nb.x, nb.y)
            if nb_key in my_dist:
                continue

            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                # If it's a tail, it will vacate unless pearl is eaten
                continue

            my_dist[nb_key] = d + 1
            queue.append((nb, d + 1))

    # BFS from enemy heads if any
    enemy_dist: Dict[Tuple[int, int], int] = {}
    if enemy_heads:
        e_queue = deque([(eh, 0) for eh in enemy_heads])
        for eh in enemy_heads:
            enemy_dist[(eh.x, eh.y)] = 0

        while e_queue and len(enemy_dist) < max_nodes * 2:
            curr, d = e_queue.popleft()
            curr_tile = ct.get_tile(curr)
            if curr_tile is None:
                continue

            for direction in Direction.get_direction_list():
                edge = curr_tile.get_edge(direction)
                if edge.get_edge_type() != EdgeType.EMPTY:
                    continue

                nb = step_pos(curr, direction, game.width, game.height)
                nb_key = (nb.x, nb.y)
                if nb_key in enemy_dist:
                    continue

                nb_tile = ct.get_tile(nb)
                if nb_tile is not None and nb_tile.get_dragon() is not None:
                    continue

                enemy_dist[nb_key] = d + 1
                e_queue.append((nb, d + 1))

    # Compare Voronoi ownership
    my_territory = 0
    controlled_pearls = 0
    for cell_key, d_my in my_dist.items():
        d_enemy = enemy_dist.get(cell_key, 999)
        if d_my <= d_enemy:
            my_territory += 1
            tile = ct.get_tile(Position(cell_key[0], cell_key[1]))
            if tile is not None and (tile.has_pearl() or tile.get_pearl_time() == 0):
                controlled_pearls += 1

    # Check tail reachability
    tail_pos = find_tail_position(ct)
    can_tail = False
    if tail_pos is not None:
        can_tail = (tail_pos.x, tail_pos.y) in my_dist

    return my_territory, controlled_pearls, can_tail
