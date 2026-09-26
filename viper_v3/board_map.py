"""
Global Persistent Board Memory and Toroidal BFS Engine for viper_v3.
Maintains known kelp edges across turns and computes full-board
chamber capacity up to 80+ nodes.
"""
from collections import deque
from typing import Set, Tuple, Dict, Optional
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos

class GlobalBoardMap:
    """Persistent across turns for each dragon."""
    def __init__(self):
        # Set of ((x, y), Direction) that have KELP
        self.kelp_edges: Set[Tuple[Tuple[int, int], str]] = set()

    def update_from_vision(self, ct: Controller) -> None:
        """Records all observed kelp edges into persistent memory."""
        for tile in ct.get_tiles():
            pos = tile.get_position()
            for d in Direction.get_direction_list():
                edge = tile.get_edge(d)
                if edge.get_edge_type() == EdgeType.KELP:
                    self.kelp_edges.add(((pos.x, pos.y), d.value))

    def is_kelp(self, pos: Position, direction: Direction) -> bool:
        return ((pos.x, pos.y), direction.value) in self.kelp_edges

    def compute_global_chamber(self, ct: Controller, game: Game, start_pos: Position,
                               max_nodes: int = 80) -> int:
        """
        Computes the reachable open chamber on the global torus grid,
        respecting all known kelp barriers and visible dragon segments.
        """
        # Collect currently known dragon segments
        dragon_cells: Set[Tuple[int, int]] = set()
        for tile in ct.get_tiles():
            if tile.get_dragon() is not None:
                p = tile.get_position()
                dragon_cells.add((p.x, p.y))

        visited: Set[Tuple[int, int]] = set()
        visited.add((start_pos.x, start_pos.y))
        queue = deque([start_pos])

        count = 0
        w, h = game.width, game.height

        while queue and count < max_nodes:
            curr = queue.popleft()
            count += 1

            for d in Direction.get_direction_list():
                # Check kelp
                if self.is_kelp(curr, d):
                    continue

                # If current tile is in vision, verify edge directly
                curr_tile = ct.get_tile(curr)
                if curr_tile is not None and curr_tile.get_edge(d).get_edge_type() == EdgeType.KELP:
                    self.kelp_edges.add(((curr.x, curr.y), d.value))
                    continue

                nb = step_pos(curr, d, w, h)
                nb_key = (nb.x, nb.y)
                if nb_key in visited or nb_key in dragon_cells:
                    continue

                visited.add(nb_key)
                queue.append(nb)

        return count
