# Dragon Game — Core Mechanics Summary

A reference for building a bot. Distilled from the full docs (overview, structure, movement, splitting, sonar,
vision, pearls, kelp/portals, death, execution-order, map-info, protocol).

**Rules changed on 2026-10-01** (after the sprint tournament): queens decide the game, and sprints have
ceil(L/4) free steps. This summary is updated for both; `docs/CHANGES_2026-10-01.md` lists every change.

## 1. Setup

- Two teams, each controlling up to **64 dragons** ("units"), snake-like creatures on a grid.
- Each dragon is its own OS process running your program, with **no shared memory** between dragons — the only
  cross-dragon communication is **sonar**.
- A game lasts at most **500 rounds**. Each round, every living dragon takes one **turn**, in **ascending dragon
  ID order**. A dragon created by a split this round is appended and acts later in the same round; a dragon that
  died earlier this round is skipped.
- Goal: grow the longest **queen** by eating pearls. Each team's queen is its initial dragon with id 0 or id 1
  (maps alternate teams line by line, so dragons 0 and 1 are on different teams). After round 500 the winner is
  decided by: (1) longer queen (a dead queen has length 0), (2) longest living dragon, (3) greatest total length
  across all your dragons, (4) draw. Ids are visible: `ID` in the init block, and every `DRAGON_BODIES` line in
  vision carries the dragon's id, so a bot knows whether it is the queen and can recognise the enemy queen on
  sight. A queen that splits keeps its id (the child gets a new id).
- A team is eliminated when all its dragons die. Game ends immediately if either team is eliminated (draw if both
  in the same round).

## 2. The Map

- Rectangular grid, width and height each 10–64. `(0,0)` is top-left; x increases right, y increases **down**.
  North is up.
- **Wraps around** (toroidal): moving off one edge brings you out the other side.
- Guaranteed **symmetric** (vertical, horizontal, or 180° rotation) for fairness — not queryable at runtime.
- Composed of **tiles** and **edges** (the boundaries between adjacent tiles, including wrap-around edges).
- Query map size via `game.get_map_size()`.

## 3. Vision

- Each dragon sees only a **7×7 window** centered on its head (Chebyshev distance ≤ 3) — 49 tiles, wrapped.
- Vision does **not** look through portals unless the far side is within 3 tiles by ordinary (non-portal)
  distance.
- For each visible tile you get: position, contents (pearl / dragon part), pearl countdown, and its 4 edges.
- `ct.get_tile(pos)` returns `None` if `pos` is outside the current window.

## 4. Kelp and Portals

Both live on **edges between tiles**, not on tiles (including edges along the map border).

- **Kelp**: a hard barrier. Moving across a kelp edge kills you (Hit Wall) and drops pearls. No other effect.
- **Portals**: paired edges sharing an ID (exactly one partner per portal). Same orientation guaranteed
  (both horizontal or both vertical). Double-sided — entering from either side teleports your head out the
  partner edge, continuing in the corresponding direction. You cannot see through a portal. Sonar **does**
  pass through portals.

## 5. Pearls (the only resource)

- Each tile has a **countdown** (visible via `get_pearl_time()`, -1 = never spawns) that decrements by 1 at the
  **start of every round**, before any dragon moves.
- At 0, the tile attempts to spawn a pearl if the tile is empty; regardless of success, it redraws a new
  countdown uniformly from a hidden per-tile `[minGap, maxGap]` range.
- On symmetric maps, mirrored tiles **share** a countdown and fire together (but only spawn on the side that's
  actually empty).
- Moving your head onto a pearl **eats it automatically**: your tail does not retract that turn, so you grow by
  1 segment. This is the only way to gain length.
- Dead dragons drop pearls (see Death).

## 6. Movement (an "action" — one action per turn)

- Standard move: one tile in a cardinal direction (`ct.make_move(Direction)`); head moves, body follows.
- **Facing**: direction from your first body segment to your head (defined similarly per-segment down the body).
- **Sprinting**: multiple moves in one turn, e.g. `ct.make_moves([N, N, E])`. The first ceil(L/4) steps are
  free, with L the length when the move starts; each step after them costs 1 body segment (moving x steps
  removes max(0, x − ceil(L/4)) segments: 5 steps cost a length-4 dragon 4 segments, a length-12 dragon 2).
  Before 2026-10-01 only the first step was free. Collision/pearl-eating is checked **at every intermediate
  step**, so the specific path matters, not just the destination (e.g. `NNE` might die where `ENN` to the same
  square survives).
- If you request more steps than you can pay for, the move is **not truncated** — you take as many steps as you
  can afford, then die paying for the next one.
- Moving backward into your own neck is legal to attempt but usually fatal.
- Only the **last action command** read for the turn is applied (MOVE/SPLIT overwrite each other).

### Collision resolution per step (order matters)

1. If not one of the first ceil(L/4) steps (L = length when the move starts), check you can pay for it (min
   length 2) — else die, "no valid action".
2. Facing is set to the step's direction; destination = tile across that edge (kelp → death; portal → exits
   partner edge; else the adjacent, wrapped tile).
3. Destination is checked against **your own body first** (including your tail — checked *before* the tail
   advances, so your own tail tile is blocked for that step), **then** other dragons. Stepping onto another
   dragon's head kills **both** of you; onto any other segment kills only you.
4. Head moves onto destination; a pearl there is eaten. Tail advances unless a pearl was eaten. If this wasn't
   one of the free steps, one more tail segment is removed (sprint cost).
5. On a multi-step move, step 2 is checked against the body **as step 1 left it** — a tile fatal as a first step
   may be safe as a second.
6. A death on any step discards remaining steps and that turn's sonar; steps already taken stand.

## 7. Splitting (the other action — one action per turn, mutually exclusive with moving)

- Creates a new dragon on your team from your **rear segments, reversed** — your old tail becomes the child's
  head, facing away from the parent. Parent keeps its front segments.
- Child gets the **next unused dragon ID**, acts later in the same round, runs as a **brand-new process with no
  memory of the parent**.
- Legal only if: child length ≥ 2 (`SPLIT 1` always illegal), parent length ≥ 2 after splitting, and team has
  <64 living dragons (`UNIT_LIMIT`).
- Illegal split → parent dies ("no valid action").
- Check legality with `ct.can_split(n)`, execute with `ct.do_split(n)`.

## 8. Sonar (only inter-dragon communication, requires protocol 3)

- Each turn, before/after your action (cast **after** the action if you survive), you may send up to 4 sonars —
  one per direction (N/E/S/W), each an unsigned 64-bit int. Sending twice in the same direction: only the last
  counts.
- Each sonar travels in a straight line from your head, wraps around the map, passes through portals, and stops
  at the first kelp or dragon part hit (friend or foe). If it hits a dragon, that dragon receives the message
  (could be yourself). Lost if it travels `WIDTH + HEIGHT` tiles with no hit.
- **Total Internal Refraction**: a sonar sent in the direction opposite your facing exits through your **tail**
  instead, in the direction the tail points.
- Received sonars are read at the **start of the recipient's next turn**. Higher-ID recipients (relative to
  sender) get it later the same round; lower-ID recipients get it the following round. No sender/team info is
  attached to a message.
- **Echoes**: at the start of your next turn you get counts of what each of your 4 sonars stopped on: `kelp`,
  `ally`, `ally_head`, `enemy`, `enemy_head`. A sonar hitting nothing adds no count to any category.
- Requires printing `PROTOCOL 3` before `ENDTURN` (see Protocol section) — otherwise you're on protocol 2 and
  miss echoes / directional sonar / 64-bit values.

## 9. Death

| Reason | Cause |
|---|---|
| Hit Wall | Moved across kelp |
| Hit Self | Moved into own body (incl. tail) |
| Hit Other Body | Moved into another dragon's non-head segment |
| Head to Head | Moved into another dragon's head — **both** die |
| No Valid Action | Unaffordable SPLIT/step, illegal split, malformed/missing command, crash, or timeout |

- Any turn where no valid action is produced defaults to **suicide**.
- On death: every second body segment starting from the head crystallizes into a pearl (length `L` → `⌈L/2⌉`
  pearls dropped); remaining sprint steps and that turn's sonar are discarded; dragon is removed from the board.
- In a head-to-head collision, resolve the "other" dragon's death sequence first, then this one's.

## 10. Turn / Round Execution Order (engine loop)

1. **Round start**: every tile's pearl countdown ticks down (top-to-bottom, left-to-right); at 0, attempts a
   spawn and redraws.
2. **Each living dragon's turn**, ascending ID order (split children appended and run later same round):
   a. Sonar inbox + echoes delivered to the bot's input, then cleared.
   b. Defaults set: action = suicide, sonars = none, indicator = none.
   c. Bot's stdout is read line-by-line until `ENDTURN`; last MOVE/SPLIT wins, last SONAR-per-direction wins,
      LOG/DOT/LINE apply immediately in print order; unparseable lines are skipped (logged) without changing
      the pending action.
   d. Action applied (see Movement/Splitting mechanics above).
   e. If still alive, sonars cast N, E, S, W.
3. **Round ends** when a team has no dragons left, or round 500 is reached.

A bot turn ends at the first of: it prints `ENDTURN`, it blocks waiting for next input, it exits, or it hits its
compute limit — the first two deliver the turn's output; the last two leave the action at default **suicide**
and restart the bot as a fresh process with a new init block.

## 11. Wire Protocol (I/O your bot must speak)

Engine writes text to your stdin, reads text from your stdout. Comments after `#` are stripped by C/C++ helpers.

**Init block** (once, at process start):
```
ID 0
TEAM A
MAP 11 11
UNIT_LIMIT 64
```

**Per-turn block**: header (`ROUND`, `DIR`, `LENGTH`, `UNIT_COUNT`, `NUM_MSGS` + that many sonar values,
`ECHOES` + 5 counts) → 49 tile lines (7×7 window, row-major, `x y hasPearl pearlIn`) → `DRAGON_BODIES` count +
lines `team id x y facing isHead` for every visible segment → 8 lines of 7 horizontal edge symbols → 7 lines of
8 vertical edge symbols (`.` open, `w` kelp, integer = portal id).

**Your reply**, ending in `ENDTURN` then implicit flush:

| Command | Args | Notes |
|---|---|---|
| `MOVE` | string of N/E/S/W letters | e.g. `MOVE NNE` = 3 steps; overwrites SPLIT |
| `SPLIT` | segment count | overwrites MOVE |
| `SONAR` | dir, uint64 | overwrites earlier SONAR in same direction |
| `PROTOCOL` | `3` | opt in to protocol 3 from next turn |
| `INDICATOR` | text | replay label, overwrites itself |
| `LOG` / `DOT` / `LINE` | — | replay-only, applied immediately, don't affect game state |

Only the **last** MOVE/SPLIT/SONAR-per-direction/INDICATOR read is used; nothing is applied until reading ends.
When your dragon's game ends, stdin closes (EOF) — exit.

## 12. Sandbox / Language Constraints (matters for what your bot can use)

- Runs in a WASM sandbox: **no network, no subprocess/fork/threads that actually run, no writable disk** (read
  only `/bot`). `os.cpu_count()`/`getpid()` return fixed values; clock is virtual (judge time), advances with
  CPU points spent — useful as a budget meter but meaningless across `sleep`.
- Randomness (`random`, `os.urandom`, `std::mt19937`, etc.) is seeded from a **per-dragon-per-game stream**, so
  replays are deterministic; seed your own generator if you want dragons to diverge.
- **Python**: CPython 3.13 + NumPy only, no third-party packages (vendor pure-Python deps). No `socket`,
  `asyncio`, `multiprocessing`, compression libs (`zlib`/`gzip`/etc.), `sqlite3`, `curses`, `subprocess`
  (raises), among others.
- **C/C++**: Clang 20, C17 / C++20, against wasi-libc / libc++, `-O2 -msimd128`; POSIX headers present but
  networking/threading/process calls fail at runtime (`ENOTSUP`).
- Each dragon gets roughly **25ms of compute per turn** (see Timeouts docs for exact CPU-point accounting).

## 13. Minimal Bot Loop (Python)

```python
import helper as unswbc

ct: unswbc.Controller
game: unswbc.Game

def execute_turn() -> None:
    ct.make_move(unswbc.Direction.NORTH)   # replace with real logic

def main() -> None:
    global ct, game
    ct, game = unswbc.init()
    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
```

`init()` reads the init block; `update()` reads the next turn's block and returns `False` when the game ends or
your dragon has died; `end_turn()` sends `ENDTURN` and flushes.
