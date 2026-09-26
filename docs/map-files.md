# Map Files

# Map Files

A.mapfile is plain text with one directive per line. Themap editorwrites them,
    and they can be written by hand.

```
MAP 11 11
SYMMETRY xy
TILE_COUNT 81
TILE 1 1 8 20
TILE 2 1 8 20
...
EDGE_COUNT 44
EDGE 0 1 -1
EDGE 12 2 3
...
DRAGON_COUNT 2
DRAGON 0 3 3 5 2 5 1 5
DRAGON 1 3 7 5 8 5 9 5
```

## Directives

### MAP width height

Required, and first. Everything after it is bounds-checked against it.

### MAP_NAME name

Optional. The visualiser and the VS Code viewer display this name.

### SYMMETRY x | y | xy

Optional. Mirrored tilesshare one pearl countdownand fire together, so a symmetric map is fair in
    timing as well as in shape. SeePearl spawns.

### TILE x y minGap maxGap

The tile's spawn range. After each attempt the tile draws its next countdown uniformly fromminGaptomaxGapinclusive. AmaxGapof 0 means the tile never spawns.TILE_COUNTmust
    match the number ofTILElines, and likewiseEDGE_COUNTandDRAGON_COUNT.

### EDGE index kind portalId

| Kind | Meaning |
| 0 | Open. |
| 1 | Kelp. Portal id-1. |
| 2 | Portal. Exactly two edges share the id, and both must have the same orientation. |

Rows of horizontal edges (a tile row's north side) alternate with rows of vertical edges (its west side). Each row
    iswidth + 1long, so the index runs to(2·height + 1)·(width + 1). The editor is the
    practical way to write these.

### DRAGON team segmentCount x y x y ...

teamis0(A) or1(B), followed by the segment count and then the
    coordinates,head first. Segments must be adjacent, on the board, and must not overlap another dragon. The
    minimum length is 2. Ids are assigned in file order from 0, which is also turn order.
