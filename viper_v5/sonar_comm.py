"""
Sonar Communication & Swarm Intelligence for viper_v5 Apex.
Packs/unpacks 64-bit sonar messages for team-wide coordination.
Includes SwarmMemory for persistent cross-turn intel.
"""
from typing import Optional, NamedTuple, Dict, List, Tuple, Set

MAGIC = 0xAF

class SonarPacket(NamedTuple):
    sender_id: int
    role: int       # 0: QUEEN, 1: ASSASSIN, 2: HARVESTER
    head_x: int
    head_y: int
    target_x: int
    target_y: int
    enemy_seen: bool
    enemy_x: int
    enemy_y: int
    length: int


def pack_sonar_message(sender_id: int, role: int, head_x: int, head_y: int,
                       target_x: int, target_y: int, enemy_seen: bool,
                       enemy_x: int, enemy_y: int, length: int) -> int:
    msg = (MAGIC & 0xFF)
    msg = (msg << 6) | (sender_id & 0x3F)
    msg = (msg << 2) | (role & 0x03)
    msg = (msg << 6) | (head_x & 0x3F)
    msg = (msg << 6) | (head_y & 0x3F)
    msg = (msg << 6) | (target_x & 0x3F)
    msg = (msg << 6) | (target_y & 0x3F)
    msg = (msg << 1) | (1 if enemy_seen else 0)
    msg = (msg << 6) | (enemy_x & 0x3F)
    msg = (msg << 6) | (enemy_y & 0x3F)
    msg = (msg << 8) | (length & 0xFF)
    return msg


def unpack_sonar_message(val: int) -> Optional[SonarPacket]:
    length = val & 0xFF
    val >>= 8
    enemy_y = val & 0x3F
    val >>= 6
    enemy_x = val & 0x3F
    val >>= 6
    enemy_seen = bool(val & 0x01)
    val >>= 1
    target_y = val & 0x3F
    val >>= 6
    target_x = val & 0x3F
    val >>= 6
    head_y = val & 0x3F
    val >>= 6
    head_x = val & 0x3F
    val >>= 6
    role = val & 0x03
    val >>= 2
    sender_id = val & 0x3F
    val >>= 6
    magic = val & 0xFF
    if magic != MAGIC:
        return None
    return SonarPacket(sender_id, role, head_x, head_y, target_x, target_y,
                       enemy_seen, enemy_x, enemy_y, length)


class SwarmMemory:
    """Persistent swarm intelligence across turns."""
    def __init__(self):
        self.teammates: Dict[int, SonarPacket] = {}
        self.enemy_sightings: List[Tuple[int, int]] = []
        self.last_enemy_round: int = -1

    def process_inbox(self, messages: List[int]) -> None:
        for val in messages:
            pkt = unpack_sonar_message(val)
            if pkt is not None:
                self.teammates[pkt.sender_id] = pkt
                if pkt.enemy_seen:
                    self.enemy_sightings.append((pkt.enemy_x, pkt.enemy_y))
                    # Keep only last 10 sightings to save memory
                    if len(self.enemy_sightings) > 10:
                        self.enemy_sightings = self.enemy_sightings[-10:]

    def get_claimed_targets(self) -> Set[Tuple[int, int]]:
        """Returns set of (x,y) tiles claimed by teammates."""
        claimed = set()
        for pkt in self.teammates.values():
            if pkt.target_x != 0 or pkt.target_y != 0:
                claimed.add((pkt.target_x, pkt.target_y))
        return claimed

    def get_teammate_positions(self) -> List[Tuple[int, int]]:
        """Returns list of known teammate head positions."""
        return [(pkt.head_x, pkt.head_y) for pkt in self.teammates.values()]
