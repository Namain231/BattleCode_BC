"""
Strategic Decision Engine for UNSW Battlecode.
Handles Queen vs Drone role assignment, Voronoi territory heuristics,
A* pathfinding, pearl targeting, and head-to-head combat trades.
"""
from typing import Tuple, List, Optional
from helper import Controller, Game, Direction, Position, EdgeType
from geometry import torus_manhattan_dist, step_pos
from safety import is_immediate_collision, get_head_hazards, compute_flood_fill
from sonar_comm import pack_sonar_message

def get_max_allowed_units(game: Game) -> int:
    """Calculates optimal swarm size based on map dimensions."""
    area = game.width * game.height
    if area < 300:
        return 2
    elif area < 800:
        return 3
    elif area < 1600:
        return 4
    else:
        return 5

def find_best_target_pearl(ct: Controller, game: Game) -> Optional[Position]:
    """
    Finds the highest priority pearl to move towards.
    Weights immediate pearls and imminent spawns (pearl_time).
    """
    head_pos = ct.get_position()
    best_score = -1.0
    best_pos = None

    for tile in ct.get_tiles():
        pos = tile.get_position()
        dist = torus_manhattan_dist(head_pos, pos, game.width, game.height)
        if dist == 0:
            continue

        score = 0.0
        if tile.has_pearl():
            score = 1000.0 / (dist + 0.5)
        elif tile.get_pearl_time() >= 0:
            p_time = tile.get_pearl_time()
            time_diff = abs(dist - p_time)
            score = 600.0 / (dist + time_diff * 2.0 + 1.0)

        if score > best_score:
            best_score = score
            best_pos = pos

    return best_pos

def evaluate_moves(ct: Controller, game: Game, is_queen: bool) -> List[Tuple[float, Direction]]:
    """
    Evaluates all 4 cardinal directions and returns a sorted list of (score, direction).
    """
    head_pos = ct.get_position()
    my_len = ct.get_length()
    curr_dir = ct.get_dir()
    enemy_hazards, friendly_hazards = get_head_hazards(ct, game)
    target_pearl = find_best_target_pearl(ct, game)

    candidates = []

    for d in Direction.get_direction_list():
        deadly, reason = is_immediate_collision(ct, game, d)
        if deadly:
            continue

        next_pos = step_pos(head_pos, d, game.width, game.height)
        score = 1000.0
        next_key = (next_pos.x, next_pos.y)

        # Deconflict with friendly dragon heads
        if next_key in friendly_hazards:
            score -= 5000.0

        # Enemy head interactions
        if next_key in enemy_hazards:
            if is_queen:
                score -= 8000.0  # Queen must NEVER risk head-to-head collision
            else:
                # Small drone: opportunistic trade if enemy is longer
                score += 1500.0 if my_len <= 3 else -4000.0

        # Flood fill chamber capacity check
        flood = compute_flood_fill(ct, game, next_pos, max_depth=max(my_len * 2 + 5, 30))
        if flood < my_len:
            # Trapped cul-de-sac!
            score -= 5000.0 * (my_len - flood)
        else:
            score += flood * 25.0

        # Progress towards targeted pearl
        if target_pearl is not None:
            old_dist = torus_manhattan_dist(head_pos, target_pearl, game.width, game.height)
            new_dist = torus_manhattan_dist(next_pos, target_pearl, game.width, game.height)
            if new_dist < old_dist:
                score += 350.0 / (new_dist + 1.0)
            else:
                score -= 80.0

        # Straight-line momentum preference (prevents zig-zag self-coiling)
        if d == curr_dir:
            score += 20.0

        candidates.append((score, d))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates

def decide_turn(ct: Controller, game: Game) -> None:
    """
    Executes the full turn decision logic for a single dragon.
    """
    my_id = ct.get_id()
    my_len = ct.get_length()
    unit_count = ct.get_unit_count()
    round_num = game.get_round_num()

    # The dragon with lowest ID or ID 0 is Queen
    is_queen = (my_id == 0 or unit_count == 1)
    max_units = get_max_allowed_units(game)

    # 1. Splitting evaluation:
    # Only Queen splits, only if length >= 12, round < 250, and unit count within map budget
    if is_queen and my_len >= 12 and round_num < 250 and unit_count < max_units:
        if ct.can_split(2):
            ct.do_split(2)
            ct.set_indicator_string(f"Q-SPLIT (len {my_len} -> {my_len - 2})")
            return

    # 2. Movement evaluation:
    candidates = evaluate_moves(ct, game, is_queen)

    if candidates:
        best_score, best_dir = candidates[0]
        ct.make_move(best_dir)
        role_tag = "QUEEN" if is_queen else "DRONE"
        ct.set_indicator_string(f"{role_tag} L{my_len} -> {best_dir.value}")
    else:
        # Emergency fallback: step in any non-instant-death direction
        for d in Direction.get_direction_list():
            deadly, _ = is_immediate_collision(ct, game, d)
            if not deadly:
                ct.make_move(d)
                return
        ct.make_move(Direction.NORTH)

    # 3. Sonar Radar ping:
    head = ct.get_position()
    msg = pack_sonar_message(my_id, 0, head.x, head.y, 0, 0, my_len)
    ct.send_sonar(ct.get_dir(), msg)
