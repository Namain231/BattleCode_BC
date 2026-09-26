# Movement

# Movement

Movement is considered a type ofactionthat a dragon can perform on a turn. Note that each dragon
    must output at least one action per turn (only thelast oneis actually performed; seeDeathfor a list of death conditions). The only other type of action which can be performed issplitting.

Movement, like all other unit actions, is performed only once the turn is complete.

## Standard Movement

Each dragon can move one tile in any cardinal direction (north, east, south, west) each turn. This causes the
        head to move in said direction, with the rest of the body following along.

Dragons can even move backwards, though doing so causes its head to squeeze into its own neck, a move which
        often proves fatal.

A dragon'sfacingdirection is the direction of its head from its first body (non-head) segment.
        The facing direction of its body segments is defined similarly (direction to the next segment towards the head).

```
ct.make_move(unswbc.Direction.EAST)
```

## Eating Pearls

When a dragon moves its head onto a pearl, the pearl is automatically eaten and the tail does not advance that
        turn. In other words, the dragon grows a body segment.

Eating pearls is the only way to gain length.

## Collisions

A dragon dies if its head moves into anyobstacles. This includeskelp, any segment of another dragon, or any segment of itself.

Note that thisdeathcondition is checked before any actual movement. This means a dragon
        will die moving into own tail, even if the tail would have moved out of the way in the same turn.

If the destination contains another dragon's head, both dragons die, regardless of their team.

```
ahead = ct.get_tile(here.add_dir(direction))
part = ahead.get_dragon() if ahead is not None else None
if part is not None:
    if part.is_head():
        continue  # both of us would die
    continue      # only I would die
```

A dragon that dies drops pearls along its body. SeeDeathfor more information.

## Sprinting

Dragons may decide to move several times in one turn in varying directions.

Although all moves happen within a single turn, collision checking (and pearl eating) is performed at every
        step. This means that in theory, a dragon might die performingNNE, but live withENN,
        even though they target the same destination.

Every additional move costs a unit segment of the sprinting dragon. More rigorously, movingxsteps in
        a turn removesx- 1 segments.

```
ct.make_moves([
    unswbc.Direction.NORTH,
    unswbc.Direction.NORTH,
    unswbc.Direction.EAST,
])
```

## Death by Sprint

A move with more steps than the dragon can pay for isnottruncated. The dragon will perform the
        steps that can be paid for, and then will pay for the next step with its own life.
