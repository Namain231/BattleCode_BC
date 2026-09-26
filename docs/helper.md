# Helper

# Helper reference

Everything the helper library gives you, taken from thehelper.pythatunswbc initput
    in your project. The helper is yours: you may edit it, or replace it with your own reader of thewire protocol.

This page follows the helper the current toolkit ships. A project made with an earlier one keeps the copy it was
    given, so if a call listed here is missing from yours, upgrade the toolkit and take the helper from a freshunswbc init. The three languages offer the same calls under each language's own names.

## Constants

What the engine is fixed at: 500 rounds, a 7x7 window, length 3 at spawn, length 2 minimum.

## Direction

One of the four compass directions.
North is up, and y grows downwards.

The protocol letter, N, E, S or W.

A fresh list of all four, north, east, south, west.

The (dx, dy) of one step this way, with y growing downwards.

The reverse direction.

A quarter turn anticlockwise.

A quarter turn clockwise.

## Team

Which side a dragon plays for.

The other team.

## Position

A tile's x and y, with (0, 0) at the top left and y growing downwards.

The position one step that way, wrapped around the map edges.

Whether these coordinates are on the board, which only matters for ones you worked out yourself.

Whether this tile is inside your 7x7 window this turn.

## Game

The board and the round number, which every dragon sees the same way.

The round being played; the game ends after 500 of them.

The map's (width, height) in tiles.

The most dragons one team may have alive at once, which is what caps splitting.

## Vision

The 7x7 block of tiles around your head, parsed as you ask for it.

All 49 tiles, row by row from the top left.

The tile at pos, or None if pos is outside the window.

## Tile

One square of the board, with whatever stands on it and its four edges.

The four edges keyed by direction.

The edge you would cross stepping that way.

The dragon segment standing here, or None if the tile is clear.

Whether a pearl is on this tile right now.

Rounds until this tile next tries to spawn a pearl, or -1 if it never does.

This tile's position on the board.

## DragonPart

One segment of a dragon, head or body.

Where this segment is.

The dragon this segment belongs to.

The team that dragon plays for.

The direction this segment faces.

Whether this is the head; stepping into another dragon's head kills both of you.

## EdgeType

What lies between two tiles: EMPTY, KELP or PORTAL.

## Edge

The boundary between two tiles.

Whether a dragon can cross this edge; kelp is the only thing that stops one.

Whether crossing this edge comes out at its partner edge.

Whether this edge is EMPTY, KELP or PORTAL.

The id this portal shares with its far edge, or -1 if this edge is not a portal.

## Controller

Your dragon: what it sees, how long it is, and the commands it sends this turn.

Segments your dragon has, counting the head.

Dragons your team has alive, this one included.

Your dragon's head segment.

Your dragon's id, which is also its place in the turn order.

The team you play for.

The way your head points at the start of this turn.

The tiles around your head.

All 49 tiles in view, row by row from the top left.

The tile at pos, or None if pos is outside the window.

Your head's position, already wrapped into the map.

Steps one tile that way; of everything you send, the last action is the one applied.

Sprints one step per direction in the list.

Whether a child of that many segments is legal this turn.

Splits that many segments off your tail.

Prints a line that shows against this turn in the replay.

Draws a dot on the replay's board, which changes nothing in the game.

Draws a line on the replay's board.

Labels your dragon with this text for the turn.

Values that reached you since your last turn, in the order they were sent.

## helper

The module itself, imported as unswbc.

Reads the spawn block and returns your (controller, game), which stay valid all match.

Reads the next turn into the controller, and returns False once the game is over or your dragon has died.

Ends the turn and flushes everything you printed.
