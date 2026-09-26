"""
Sonar Communication & Radar Module for UNSW Battlecode.
Packs and unpacks 64-bit unsigned integers for team-wide swarm coordination.
"""
from typing import Optional, NamedTuple

MAGIC = 0xA5  # Team signature to filter out random enemy sonar

class SonarPacket(NamedTuple):
    sender_id: int
    msg_type: int   # 0: STATUS, 1: ENEMY_ALERT, 2: PEARL_CLAIM
    head_x: int
    head_y: int
    extra_x: int
    extra_y: int
    length: int

def pack_sonar_message(sender_id: int, msg_type: int, head_x: int, head_y: int,
                       extra_x: int, extra_y: int, length: int) -> int:
    """Pack status/alert into a 64-bit integer."""
    msg = (MAGIC & 0xFF)
    msg = (msg << 6) | (sender_id & 0x3F)
    msg = (msg << 2) | (msg_type & 0x03)
    msg = (msg << 6) | (head_x & 0x3F)
    msg = (msg << 6) | (head_y & 0x3F)
    msg = (msg << 6) | (extra_x & 0x3F)
    msg = (msg << 6) | (extra_y & 0x3F)
    msg = (msg << 8) | (length & 0xFF)
    return msg

def unpack_sonar_message(val: int) -> Optional[SonarPacket]:
    """Unpack a 64-bit integer into a SonarPacket if magic matches."""
    length = val & 0xFF
    val >>= 8
    extra_y = val & 0x3F
    val >>= 6
    extra_x = val & 0x3F
    val >>= 6
    head_y = val & 0x3F
    val >>= 6
    head_x = val & 0x3F
    val >>= 6
    msg_type = val & 0x03
    val >>= 2
    sender_id = val & 0x3F
    val >>= 6
    magic = val & 0xFF
    if magic != MAGIC:
        return None
    return SonarPacket(sender_id, msg_type, head_x, head_y, extra_x, extra_y, length)
