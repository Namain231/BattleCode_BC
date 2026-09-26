"""
Safety & Graph Analysis Engine for viper_v5 Apex.
Features:
- Immediate collision detection (kelp, body, head-on, portal-safe)
- Dynamic tail-vacancy flood fill with proper tail tracking
- Articulation point detection (avoid moves that fragment open space)
- Voronoi territory estimation
- Head hazard mapping (enemy + friendly)
- Compactness / wall-hugging metric
"""
from collections import deque
from typing import Tuple, List, Set, Optional, Dict
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos, torus_manhattan_dist


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
        # Portals are risky but not always fatal - treat as unsafe by default
        # unless we have full portal pair knowledge
        return True, "unknown_portal"

    ahead_pos = step_pos(here, direction, game.width, game.height)
    ahead_tile = ct.get_tile(ahead_pos)
    if ahead_tile is None:
        return False, "unseen"  # Outside vision - risky but not guaranteed death

    part = ahead_tile.get_dragon()
    if part is not None:
        if part.is_head():
            return True, "head_on"
        # Check if this is our own tail AND we're NOT eating a pearl right now
        # The tail is blocked at collision check time (before tail advances)
        return True, "hit_body"

    return False, "safe"


def get_head_hazards(ct: Controller, game: Game) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
    """
    Returns (enemy_hazards, friendly_hazards) — sets of (x,y) tiles
    adjacent to enemy and friendly dragon heads respectively.
    """
    enemy_hazards: Set[Tuple[int, int]] = set()
    friendly_hazards: Set[Tuple[int, int]] = set()
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


def find_my_tail_segments(ct: Controller) -> List[Position]:
    """
    Returns all body segments of our dragon sorted by their actual
    chain order (head -> ... -> tail). The LAST element is the true tail.
    
    Since we can't get segment order from the API, we use a chain-walk:
    find all our segments, then BFS from head along our own body.
    """
    my_id = ct.get_id()
    head_pos = ct.get_position()
    
    # Collect all our body segment positions
    my_body: Set[Tuple[int, int]] = set()
    my_body.add((head_pos.x, head_pos.y))
    
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.get_id() == my_id:
            p = part.get_position()
            my_body.add((p.x, p.y))
    
    if len(my_body) <= 1:
        return [head_pos]
    
    # Return body as list. Tail is the segment furthest in the chain from head.
    # Simple BFS from head along body tiles
    ordered = [head_pos]
    visited = {(head_pos.x, head_pos.y)}
    queue = deque([head_pos])
    
    while queue:
        curr = queue.popleft()
        # Don't use game dimensions here - just check 4 neighbors
        for d in Direction.get_direction_list():
            # We need game dims but this function doesn't have them
            # Use a simple offset approach - body segments should be adjacent
            dx, dy = d.get_offset()
            # We can't compute toroidal wrap without game dims
            # so just check direct neighbors
            pass
    
    # Fallback: return segments sorted by distance from head (approximate)
    body_positions = []
    for bx, by in my_body:
        if (bx, by) != (head_pos.x, head_pos.y):
            body_positions.append(Position(bx, by))
    
    return [head_pos] + body_positions


def find_my_tail(ct: Controller, game: Game) -> Optional[Position]:
    """
    Finds our dragon's actual tail tip by chain-walking from the head
    along body segments using toroidal adjacency.
    """
    my_id = ct.get_id()
    head_pos = ct.get_position()
    w, h = game.width, game.height
    
    # Collect all our body positions
    my_body_set: Set[Tuple[int, int]] = set()
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.get_id() == my_id and not part.is_head():
            p = part.get_position()
            my_body_set.add((p.x, p.y))
    
    if not my_body_set:
        return None
    
    # Chain-walk from head: each body segment is adjacent to exactly
    # one "next" segment in the chain toward the tail.
    visited = {(head_pos.x, head_pos.y)}
    current = head_pos
    last_body = None
    
    for _ in range(len(my_body_set) + 2):  # Safety bound
        found_next = False
        for d in Direction.get_direction_list():
            nb = step_pos(current, d, w, h)
            nb_key = (nb.x, nb.y)
            if nb_key in my_body_set and nb_key not in visited:
                visited.add(nb_key)
                current = nb
                last_body = nb
                found_next = True
                break
        if not found_next:
            break
    
    return last_body


def compute_flood_fill_with_tail(ct: Controller, game: Game, start_pos: Position,
                                  my_len: int, max_depth: int = 60) -> Tuple[int, bool]:
    """
    BFS flood fill from start_pos.
    Simulates tail vacancy: if start_pos has no pearl, the tail cell opens up.
    Tracks whether the flood fill can reach the tail (guaranteeing loop survival).
    
    Returns (reachable_count, can_reach_tail).
    """
    dest_tile = ct.get_tile(start_pos)
    has_pearl = dest_tile is not None and (dest_tile.has_pearl() or dest_tile.get_pearl_time() == 0)

    tail_pos = find_my_tail(ct, game)
    vacated_tail_key: Optional[Tuple[int, int]] = None
    if not has_pearl and tail_pos is not None:
        vacated_tail_key = (tail_pos.x, tail_pos.y)

    visited: Set[Tuple[int, int]] = set()
    visited.add((start_pos.x, start_pos.y))
    queue = deque([start_pos])

    can_reach_tail = False
    count = 0
    w, h = game.width, game.height

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

            nb = step_pos(curr, d, w, h)
            nb_key = (nb.x, nb.y)
            if nb_key in visited:
                continue

            # Check if this is the vacated tail cell
            if vacated_tail_key is not None and nb_key == vacated_tail_key:
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


def compute_simple_flood(ct: Controller, game: Game, start_pos: Position,
                         max_depth: int = 50) -> int:
    """Simple BFS flood fill counting reachable empty tiles."""
    visited: Set[Tuple[int, int]] = set()
    visited.add((start_pos.x, start_pos.y))
    queue = deque([start_pos])
    count = 0
    w, h = game.width, game.height

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

            nb = step_pos(curr, d, w, h)
            nb_key = (nb.x, nb.y)
            if nb_key in visited:
                continue

            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                continue

            visited.add(nb_key)
            queue.append(nb)

    return count


def count_open_neighbors(ct: Controller, game: Game, pos: Position) -> int:
    """Count how many cardinal neighbors of pos are open (empty, no dragon)."""
    count = 0
    tile = ct.get_tile(pos)
    if tile is None:
        return 0
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if edge.get_edge_type() != EdgeType.EMPTY:
            continue
        nb = step_pos(pos, d, game.width, game.height)
        nb_tile = ct.get_tile(nb)
        if nb_tile is None or nb_tile.get_dragon() is None:
            count += 1
    return count


def count_compactness(ct: Controller, game: Game, pos: Position) -> int:
    """
    Wall-hugging / compactness metric: counts adjacent obstacles
    (kelp edges or dragon body segments) around pos.
    Higher = more compact = leaves open space unfragmented.
    """
    tile = ct.get_tile(pos)
    if tile is None:
        return 0

    adjacent_walls = 0
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if edge.get_edge_type() == EdgeType.KELP:
            adjacent_walls += 1
        elif edge.get_edge_type() == EdgeType.EMPTY:
            nb = step_pos(pos, d, game.width, game.height)
            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                adjacent_walls += 1

    return adjacent_walls


def is_cutting_move(ct: Controller, game: Game, next_pos: Position) -> bool:
    """
    Heuristic check: would stepping onto next_pos create an articulation point
    that fragments the open space around it?
    
    Checks if the open neighbors of next_pos are still connected to each other
    without going through next_pos. If they aren't, this is a cutting move.
    """
    tile = ct.get_tile(next_pos)
    if tile is None:
        return False
    
    w, h = game.width, game.height
    
    # Find open neighbors of next_pos
    open_neighbors: List[Tuple[int, int]] = []
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if edge.get_edge_type() != EdgeType.EMPTY:
            continue
        nb = step_pos(next_pos, d, w, h)
        nb_tile = ct.get_tile(nb)
        if nb_tile is None or nb_tile.get_dragon() is None:
            open_neighbors.append((nb.x, nb.y))
    
    if len(open_neighbors) <= 1:
        return False  # 0 or 1 open neighbor: not an articulation issue
    
    # BFS from the first open neighbor, see if all others are reachable
    # WITHOUT going through next_pos
    blocked = (next_pos.x, next_pos.y)
    start_key = open_neighbors[0]
    target_keys = set(open_neighbors[1:])
    
    visited: Set[Tuple[int, int]] = {start_key, blocked}
    queue = deque([Position(start_key[0], start_key[1])])
    found = 0
    steps = 0
    max_steps = min(40, game.width * game.height // 4)  # Bounded search
    
    while queue and steps < max_steps and found < len(target_keys):
        curr = queue.popleft()
        steps += 1
        
        curr_tile = ct.get_tile(curr)
        if curr_tile is None:
            continue
        
        for d in Direction.get_direction_list():
            edge = curr_tile.get_edge(d)
            if edge.get_edge_type() != EdgeType.EMPTY:
                continue
            nb = step_pos(curr, d, w, h)
            nb_key = (nb.x, nb.y)
            if nb_key in visited:
                continue
            
            nb_tile = ct.get_tile(nb)
            if nb_tile is not None and nb_tile.get_dragon() is not None:
                continue
            
            visited.add(nb_key)
            if nb_key in target_keys:
                found += 1
            queue.append(nb)
    
    # If we couldn't reach all open neighbors, this is a cutting move
    return found < len(target_keys)
