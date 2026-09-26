# Protocol

# Wire protocol

Version3.0.0. The engine writes plain text to the bot's stdin and reads plain text from its
    stdout. The helper library only parses and prints this format and may be replaced. Blank lines may be skipped, and
    the C and C++ helpers strip anything after#.

## Init block

Sent once, when the process starts.

```
ID 0
TEAM A
MAP 11 11
UNIT_LIMIT 64
```

- ID: the dragon's id, unique within the game.
- TEAM:AorB.
- MAP: width, then height.
- UNIT_LIMIT: the maximum number of living dragons per team. Default 64.

A split child and a restarted bot each receive their own init block. It marks the start of a process, not the start
    of the game.

## Round block

Sent once per turn, in this order.

### 1. Header

```
ROUND 12
DIR N
LENGTH 5
UNIT_COUNT 2
NUM_MSGS 1
90210
ECHOES 0 1 0 0 1
```

ROUND,DIR(the dragon's facing),LENGTH,UNIT_COUNT(living
    dragons on the dragon's team), andNUM_MSGS, followed by that many lines, each one unsigned 64-bitsonarvalue. ThenECHOESand five counts of what the dragon's sonars stopped
    on last turn: kelp, ally, ally head, enemy, enemy head. A ray that stopped on nothing adds no count. A dragon getsECHOESand values above 4294967295 only after its reply has hadPROTOCOL 3.

### 2. Tiles, 49 lines

```
2 1 0 -1
3 1 1 8
4 1 0 3
...
```

The 7×7 window, row by row. Row 0 is three tiles north of the head, and column 0 is three tiles west. Each line isx y hasPearl pearlIn. Coordinates are already wrapped.pearlInis −1 for a tile that never spawns.

### 3. Dragon bodies

```
DRAGON_BODIES 4
A 0 5 4 N 1
A 0 5 5 N 0
B 1 7 3 W 1
B 1 8 3 W 0
```

DRAGON_BODIESand a count, then one lineteam id x y facing isHeadfor every segment of every
    living dragon inside the window, the bot's own included. A head's facing is its heading; a body segment's facing points
    towards the head.

### 4. Horizontal edges, 8 lines of 7

```
. . . . . . .
. . w w . . .
. . . . . . .
. . . . . . .
. . . 3 . . .
. . . . . . .
. . . . . . .
. . . . . . .
```

The north edge of each row of tiles, then the south edge of the last row.

### 5. Vertical edges, 7 lines of 8

```
. . . . . . . .
. . . . . . . .
. w . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
```

The west edge of each column of tiles, then the east edge of the last column.

### Edge symbols

| Symbol | Meaning |
| . | Open. |
| w | Kelp. |
| An integer | A portal. The other edge with that id is the far end. |

Split on whitespace, since a portal id may have more than one digit.

## Reply

Lines to stdout, ending withENDTURN, then a flush. One flush per turn is the cheap way (seeTimeouts).

| Command | Arguments | Effect |
| MOVE | N/E/S/Wletters | Action: move.MOVE NNEis three steps. |
| SPLIT | Segment count | Action: split off the rear segments. |
| SONAR | N/E/S/W, then an unsigned 64-bit integer | Ping that way after the action. |
| PROTOCOL | 3 | Protocol 3 input from the next turn. |
| INDICATOR | Text | Label on the dragon this turn. |
| LOG | Text | Message attached to this turn. |
| DOT | x y r g b | Dot on the board in the replay. |
| LINE | x1 y1 x2 y2 r g b | Line on the board in the replay. |
| ENDTURN |  | Stop reading. |

MOVEandSPLIToverwrite each other, aSONARoverwrites an earlier one in the
    same direction, andINDICATORoverwritesINDICATOR. The last one read takes effect. The
    drawing commands are applied as they are read. SeeExecution orderfor the exact sequence.

## Ending

When the game ends for a dragon, the engine closes its stdin. Reading a line then returns EOF, and the process
    should exit. The helpers also stop onENDGAME, which the current engine does not send.
