"""
Viper V5 APEX — Master Strategy Engine (Tuned).

Key breakthroughs over V3/V4:
1. Articulation Point Avoidance: Never step on a tile that fragments open space.
2. Dual Flood Fill: Fast simple flood + tail-vacancy flood for accurate chamber eval.
3. Smarter Splitting: Size-3 children (more viable), tight round limits.
4. Aggressive Pearl Greed: Higher pearl priority to win length tiebreaks.
5. Endgame Awareness: After round 380, Queen focuses on survival.
6. Exit-count heuristic: Strongly avoid 0- and 1-exit tiles.
7. Improved Assassin Logic: Drones hunt only when confident of head-on opportunity.
"""
from typing import Tuple, List, Optional
from helper import Controller, Game, Direction, Position, EdgeType
from geometry import torus_manhattan_dist, step_pos
from safety import (
    is_immediate_collision,
    get_head_hazards,
    compute_flood_fill_with_tail,
    compute_simple_flood,
    count_compactness,
    count_open_neighbors,
    is_cutting_move,
)
from sonar_comm import pack_sonar_message


def get_max_allowed_units(game: Game) -> int:
    """Adaptive swarm size based on map area."""
    area = game.width * game.height
    if area < 200:
        return 2
    elif area < 400:
        return 3
    elif area < 900:
        return 4
    else:
        return 5


def find_enemy_heads(ct: Controller, my_team) -> List[Tuple[int, Position, int]]:
    """Finds all visible enemy dragon heads with estimated length."""
    enemies = []
    enemy_segments: dict = {}
    
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.get_team() != my_team:
            eid = part.get_id()
            enemy_segments[eid] = enemy_segments.get(eid, 0) + 1
    
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != my_team:
            eid = part.get_id()
            est_len = enemy_segments.get(eid, 1)
            enemies.append((eid, part.get_position(), est_len))
    
    return enemies


def find_best_target_pearl(ct: Controller, game: Game) -> Optional[Tuple[Position, float]]:
    """Finds best target pearl with teammate deconfliction."""
    head_pos = ct.get_position()
    my_id = ct.get_id()
    my_team = ct.get_team()

    friendly_heads = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() == my_team:
            if part.get_id() != my_id:
                friendly_heads.append((part.get_id(), part.get_position()))

    best_score = -1.0
    best_pos = None

    for tile in ct.get_tiles():
        pos = tile.get_position()
        dist = torus_manhattan_dist(head_pos, pos, game.width, game.height)
        if dist == 0:
            continue

        # Deconfliction: yield to closer or lower-ID teammate
        claimed = False
        for f_id, f_pos in friendly_heads:
            f_dist = torus_manhattan_dist(f_pos, pos, game.width, game.height)
            if f_dist < dist or (f_dist == dist and f_id < my_id):
                claimed = True
                break
        if claimed:
            continue

        score = 0.0
        if tile.has_pearl():
            score = 2000.0 / (dist + 0.5)
        elif tile.get_pearl_time() >= 0:
            p_time = tile.get_pearl_time()
            time_diff = abs(dist - p_time)
            score = 1000.0 / (dist + time_diff * 1.5 + 1.0)

        if score > best_score:
            best_score = score
            best_pos = pos

    # Fallback
    if best_pos is None:
        for tile in ct.get_tiles():
            if tile.has_pearl():
                pos = tile.get_position()
                dist = torus_manhattan_dist(head_pos, pos, game.width, game.height)
                score = 1200.0 / (dist + 1.0)
                if score > best_score:
                    best_score = score
                    best_pos = pos

    if best_pos is not None:
        return best_pos, best_score
    return None


def evaluate_moves(ct: Controller, game: Game, is_queen: bool,
                   round_num: int) -> List[Tuple[float, Direction]]:
    """Evaluates all 4 cardinal moves and returns scored candidates."""
    head_pos = ct.get_position()
    my_len = ct.get_length()
    curr_dir = ct.get_dir()
    w, h = game.width, game.height
    
    enemy_hazards, friendly_hazards = get_head_hazards(ct, game)
    pearl_result = find_best_target_pearl(ct, game)
    target_pearl = pearl_result[0] if pearl_result else None
    
    enemy_heads = find_enemy_heads(ct, ct.get_team())
    
    endgame = round_num > 380
    
    candidates = []
    
    flood_depth = max(my_len * 2 + 10, 50)

    for d in Direction.get_direction_list():
        deadly, reason = is_immediate_collision(ct, game, d)
        if deadly:
            continue

        next_pos = step_pos(head_pos, d, w, h)
        next_key = (next_pos.x, next_pos.y)

        score = 1000.0

        # ====== SURVIVAL ======
        
        # Strict friendly deconfliction
        if next_key in friendly_hazards:
            score -= 50000.0

        # Enemy head interactions
        if next_key in enemy_hazards:
            if is_queen:
                penalty = -30000.0 if endgame else -18000.0
                score += penalty
            else:
                if my_len <= 3:
                    assassination_value = 0.0
                    for _, e_pos, e_len in enemy_heads:
                        if torus_manhattan_dist(next_pos, e_pos, w, h) <= 1:
                            assassination_value = max(assassination_value, e_len * 250.0)
                    if assassination_value > 0:
                        score += assassination_value
                    else:
                        score -= 6000.0
                else:
                    score -= 12000.0

        # Chamber capacity via flood fill with tail vacancy simulation
        chamber, can_reach_tail = compute_flood_fill_with_tail(
            ct, game, next_pos, my_len, max_depth=flood_depth
        )

        if chamber < my_len:
            if can_reach_tail:
                if chamber < my_len // 3:
                    score -= 4000.0  # Very tight loop is still dangerous
                else:
                    score += 600.0
            else:
                # True dead-end: catastrophic penalty
                score -= 15000.0 * (my_len - chamber)
        else:
            # Open space bonus with diminishing returns
            overflow = chamber - my_len
            score += min(chamber * 25.0 + overflow * 10.0, 3000.0)

        # Articulation point penalty
        if is_cutting_move(ct, game, next_pos):
            score -= 4000.0

        # Open exits from next position
        open_exits = count_open_neighbors(ct, game, next_pos)
        if open_exits == 0:
            score -= 10000.0
        elif open_exits == 1:
            score -= 2500.0  # Corridor: dangerous
        else:
            score += open_exits * 80.0

        # ====== SPACE CONTROL ======
        
        compactness = count_compactness(ct, game, next_pos)
        score += compactness * 20.0

        # ====== PEARL COLLECTION ======
        
        if target_pearl is not None:
            old_dist = torus_manhattan_dist(head_pos, target_pearl, w, h)
            new_dist = torus_manhattan_dist(next_pos, target_pearl, w, h)
            if new_dist < old_dist:
                pearl_bonus = 700.0 / (new_dist + 1.0)
                if endgame and is_queen:
                    pearl_bonus *= 0.4
                score += pearl_bonus
            else:
                score -= 80.0

        # ====== ASSASSINATION ======
        
        if not is_queen and my_len <= 3 and enemy_heads:
            for _, e_pos, e_len in enemy_heads:
                old_e_dist = torus_manhattan_dist(head_pos, e_pos, w, h)
                new_e_dist = torus_manhattan_dist(next_pos, e_pos, w, h)
                if new_e_dist < old_e_dist and e_len >= 5:
                    score += 500.0 / (new_e_dist + 1.0)

        # ====== MOMENTUM ======
        if d == curr_dir:
            score += 15.0

        candidates.append((score, d))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates


def get_failsafe_direction(ct: Controller, game: Game) -> Direction:
    """Last-resort direction picker."""
    head = ct.get_position()
    tile = ct.get_tile(head)
    if tile is not None:
        for d in Direction.get_direction_list():
            if tile.get_edge(d).get_edge_type() == EdgeType.EMPTY:
                nb = step_pos(head, d, game.width, game.height)
                nb_tile = ct.get_tile(nb)
                if nb_tile is None or nb_tile.get_dragon() is None:
                    return d
        for d in Direction.get_direction_list():
            if tile.get_edge(d).get_edge_type() == EdgeType.EMPTY:
                return d
    return Direction.NORTH


def decide_turn(ct: Controller, game: Game) -> None:
    """Main turn decision function."""
    my_id = ct.get_id()
    my_len = ct.get_length()
    unit_count = ct.get_unit_count()
    round_num = game.get_round_num()
    
    is_queen = (my_id == 0 or unit_count == 1)
    
    area = game.width * game.height
    if area < 200:
        max_units = 2
    elif area < 400:
        max_units = 3
    elif area < 900:
        max_units = 4
    else:
        max_units = 5

    # 1. Splitting
    if is_queen and unit_count < max_units and round_num < 200:
        if my_len >= 10:
            if ct.can_split(3):
                ct.do_split(3)
                ct.set_indicator_string(f"V5-SPLIT3 ({my_len} -> {my_len - 3})")
                return
        if my_len >= 8:
            if ct.can_split(2):
                ct.do_split(2)
                ct.set_indicator_string(f"V5-SPLIT2 ({my_len} -> {my_len - 2})")
                return

    # 2. Movement
    candidates = evaluate_moves(ct, game, is_queen, round_num)

    if candidates:
        best_score, best_dir = candidates[0]
        ct.make_move(best_dir)
        role = "V5-Q" if is_queen else f"V5-D"
        ct.set_indicator_string(f"{role} L{my_len} S{best_score:.0f}")
    else:
        ct.make_move(get_failsafe_direction(ct, game))
        ct.set_indicator_string("V5-FAILSAFE")

    # 3. Sonar broadcast
    head = ct.get_position()
    pearl_result = find_best_target_pearl(ct, game)
    tx, ty = 0, 0
    if pearl_result:
        tx, ty = pearl_result[0].x, pearl_result[0].y
    
    enemy_heads = find_enemy_heads(ct, ct.get_team())
    enemy_seen = len(enemy_heads) > 0
    ex, ey = 0, 0
    if enemy_seen:
        _, e_pos, _ = enemy_heads[0]
        ex, ey = e_pos.x, e_pos.y
    
    role_code = 0 if is_queen else 1
    msg = pack_sonar_message(my_id, role_code, head.x, head.y, tx, ty,
                             enemy_seen, ex, ey, my_len)
    ct.send_sonar(ct.get_dir(), msg)
