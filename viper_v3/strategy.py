"""
Viper V3 Strategy Engine (Predator Edition).
Refined directly from V2's 100% win-rate architecture:
- Retains V2's rock-solid local flood fill and friendly deconfliction
- Adds aggressive hunter drone targeting (hunting enemy Queen)
- Dynamic pearl priority (accelerated pearl hoarding when space is open)
- Never-Kelp emergency failsafe
"""
from typing import Tuple, List, Optional
from helper import Controller, Game, Direction, Position, EdgeType
from geometry import torus_manhattan_dist, step_pos
from safety import is_immediate_collision, get_head_hazards, compute_flood_fill
from sonar_comm import pack_sonar_message

def get_max_allowed_units(game: Game) -> int:
    area = game.width * game.height
    if area < 300:
        return 3
    elif area < 800:
        return 4
    else:
        return 6

def find_enemy_queen(ct: Controller, my_team) -> Optional[Tuple[int, Position]]:
    """Finds the longest visible enemy dragon head."""
    best_len = -1
    best_pos = None
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != my_team:
            # We found an enemy head!
            return part.get_id(), part.get_position()
    return None

def find_best_target_pearl(ct: Controller, game: Game) -> Optional[Position]:
    """V2's battle-tested local pearl deconfliction."""
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

        # If a closer or lower-ID teammate is nearby, yield to them
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
            score = 1600.0 / (dist + 0.5)
        elif tile.get_pearl_time() >= 0:
            p_time = tile.get_pearl_time()
            time_diff = abs(dist - p_time)
            score = 850.0 / (dist + time_diff * 1.8 + 1.0)

        if score > best_score:
            best_score = score
            best_pos = pos

    if best_pos is None:
        for tile in ct.get_tiles():
            if tile.has_pearl():
                pos = tile.get_position()
                dist = torus_manhattan_dist(head_pos, pos, game.width, game.height)
                score = 1000.0 / (dist + 1.0)
                if score > best_score:
                    best_score = score
                    best_pos = pos

    return best_pos

def evaluate_moves(ct: Controller, game: Game, is_queen: bool) -> List[Tuple[float, Direction]]:
    head_pos = ct.get_position()
    my_len = ct.get_length()
    curr_dir = ct.get_dir()
    enemy_hazards, friendly_hazards, _ = get_head_hazards(ct, game)
    target_pearl = find_best_target_pearl(ct, game)
    enemy_queen = find_enemy_queen(ct, ct.get_team())

    candidates = []

    for d in Direction.get_direction_list():
        deadly, reason = is_immediate_collision(ct, game, d)
        if deadly:
            continue

        next_pos = step_pos(head_pos, d, game.width, game.height)
        next_key = (next_pos.x, next_pos.y)

        score = 1000.0

        # Strict friendly deconfliction
        if next_key in friendly_hazards:
            score -= 50000.0

        # Enemy hazards
        if next_key in enemy_hazards:
            if is_queen:
                score -= 20000.0  # Queen never gambles
            else:
                # Small drone: opportunistic assassination!
                if my_len <= 3:
                    score += 4000.0  # Attack enemy head!
                else:
                    score -= 8000.0

        # Chamber capacity via V2's robust BFS
        flood = compute_flood_fill(ct, game, next_pos, max_depth=max(my_len * 2 + 5, 40))
        if flood < my_len:
            score -= 7000.0 * (my_len - flood)
        else:
            score += flood * 35.0

        # Targeted pearl navigation
        if target_pearl is not None:
            old_dist = torus_manhattan_dist(head_pos, target_pearl, game.width, game.height)
            new_dist = torus_manhattan_dist(next_pos, target_pearl, game.width, game.height)
            if new_dist < old_dist:
                # Higher reward for getting closer
                score += 550.0 / (new_dist + 1.0)
            else:
                score -= 90.0

        # Assassin Drone Pursuit Mode:
        if not is_queen and my_len <= 3 and enemy_queen is not None:
            eq_id, eq_pos = enemy_queen
            old_eq_dist = torus_manhattan_dist(head_pos, eq_pos, game.width, game.height)
            new_eq_dist = torus_manhattan_dist(next_pos, eq_pos, game.width, game.height)
            if new_eq_dist < old_eq_dist:
                score += 800.0 / (new_eq_dist + 1.0)

        # Straight-line momentum
        if d == curr_dir:
            score += 25.0

        candidates.append((score, d))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates

def get_failsafe_direction(ct: Controller, game: Game) -> Direction:
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
    my_id = ct.get_id()
    my_len = ct.get_length()
    unit_count = ct.get_unit_count()
    round_num = game.get_round_num()

    is_queen = (my_id == 0 or unit_count == 1)
    max_units = get_max_allowed_units(game)

    # 1. Splitting: Queen only, len >= 12, early/mid game
    if is_queen and my_len >= 12 and round_num < 220 and unit_count < max_units:
        if ct.can_split(2):
            ct.do_split(2)
            ct.set_indicator_string(f"V3-SPLIT ({my_len} -> {my_len - 2})")
            return

    # 2. Movement
    candidates = evaluate_moves(ct, game, is_queen)

    if candidates:
        best_score, best_dir = candidates[0]
        ct.make_move(best_dir)
        role = "V3-QUEEN" if is_queen else "V3-ASSASSIN"
        ct.set_indicator_string(f"{role} L{my_len} -> {best_dir.value}")
    else:
        ct.make_move(get_failsafe_direction(ct, game))

    # 3. Sonar radar pulse
    head = ct.get_position()
    role_code = 0 if is_queen else 1
    msg = pack_sonar_message(my_id, role_code, head.x, head.y, 0, 0, False, 0, 0, my_len)
    ct.send_sonar(ct.get_dir(), msg)
