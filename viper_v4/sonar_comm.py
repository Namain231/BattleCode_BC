"""
Sonar Communication for viper_v4.
Packs and unpacks 64-bit unsigned integers for swarm coordination.
"""
from typing import Optional, NamedTuple

MAGIC = 0xEA

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
    return SonarPacket(sender_id, role, head_x, head_y, target_x, target_y, enemy_seen, enemy_x, enemy_y, length)
