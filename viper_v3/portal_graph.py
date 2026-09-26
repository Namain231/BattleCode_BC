"""
Portal Discovery & Wormhole Graph for viper_v3.
Tracks portal locations, pairs matching portal IDs, and computes
exact teleport destinations.
"""
from typing import Dict, List, Tuple, Optional
from helper import Controller, Game, Direction, EdgeType, Position
from geometry import step_pos

class PortalEdge:
    __slots__ = ("portal_id", "pos", "direction", "is_horizontal")
    def __init__(self, portal_id: int, pos: Position, direction: Direction, is_horizontal: bool):
        self.portal_id = portal_id
        self.pos = pos
        self.direction = direction
        self.is_horizontal = is_horizontal

class PortalRegistry:
    """Persistent registry of all discovered portals across turns."""
    def __init__(self):
        # portal_id -> list of PortalEdge (up to 2)
        self.portals: Dict[int, List[PortalEdge]] = {}

    def scan_vision(self, ct: Controller) -> None:
        """Inspects current vision for portal edges and registers them."""
        for tile in ct.get_tiles():
            pos = tile.get_position()
            for d in Direction.get_direction_list():
                edge = tile.get_edge(d)
                if edge.get_edge_type() == EdgeType.PORTAL:
                    pid = edge.get_portal_id()
                    if pid < 0:
                        continue
                    # Check if already registered
                    if pid not in self.portals:
                        self.portals[pid] = []
                    
                    already = False
                    for existing in self.portals[pid]:
                        if existing.pos == pos and existing.direction == d:
                            already = True
                            break
                    if not already:
                        self.portals[pid].append(PortalEdge(pid, pos, d, edge.is_horizontal))

    def get_teleport_destination(self, from_pos: Position, direction: Direction,
                                 portal_id: int, game: Game) -> Optional[Position]:
        """
        If both ends of portal_id are known, returns the destination Position
        after stepping through the portal in direction.
        """
        ends = self.portals.get(portal_id, [])
        if len(ends) < 2:
            return None  # Partner portal not yet located

        # Identify partner end
        partner = None
        for pe in ends:
            if pe.pos != from_pos:
                partner = pe
                break
        if partner is None:
            return None

        # Emerge in the same direction from partner edge
        return step_pos(partner.pos, direction, game.width, game.height)
