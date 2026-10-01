# Splitting

> Source: https://game.battlecode.au/docs/splitting (fetched 2026-10-01, after the queen rule change)

Splitting is another **action** that dragons can perform. A dragon can only perform one action per turn.

*Demo replay: A length 6 dragon splits. The parent continues east. The child leaves west, head first, from the old tail.*

A dragon may split itself to create a new dragon on its team. Note that the minimum length for any dragon is 2. The child consists of the parent's rear segments in reverse order, so the parent's old tail becomes the child's head and the child faces away from the parent.

The child receives the next unused dragon id, and takes its first turn later in the same round. The child is controlled by a brand new instance of your program, and has no memory of the parent.

## Constraints

A split is legal only if all of the following hold:

1. The child has length at least 2. `SPLIT 1` is never legal.
2. The parent has length at least 2 after the split. A dragon of length 6 may split 2, 3 or 4.
3. The team has fewer than 64 living dragons.

Requesting an illegal split kills the parent with *no valid action*.

```
if ct.can_split(2):
    ct.do_split(2)
else:
    ct.make_move(unswbc.Direction.NORTH)
```
