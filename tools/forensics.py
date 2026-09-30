"""Replay forensics: compare growth and death causes for our and top-team games.

    python tools/forensics.py --n 25

The script decodes one replay at a time and does not use replay.py's disk cache.
Death categories are counted per game; contact attribution is marked unknown when
the replay does not expose enough position information to identify the other dragon.
"""
import argparse
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from replay import _decode, DEATHS  # noqa: E402

OPEN_MAPS = {"portals", "slithery fight", "schooltime"}
CHECKPOINTS = (100, 200, 300, 350, 400)
PHASES = ((0, 100), (100, 300), (300, 500))
BUCKETS = ((2, 3, "2-3"), (4, 6, "4-6"), (7, 10**9, "7+"))
CONTACT_CAUSES = ("head to head", "hit other body")
CAUSES = [r for r in DEATHS if r not in CONTACT_CAUSES]
CAUSES.append("unknown")
for _reason in CONTACT_CAUSES:
    CAUSES.extend(f"{_reason} {team}" for team in ("ally", "enemy", "unknown"))


def map_name(text):
    lines = text.splitlines()
    return next((line.split(" ", 1)[1].strip() for line in lines
                 if line.startswith("MAP_NAME ")), lines[0].strip() if lines else "?")


def map_class(name):
    return "open" if name.strip().lower() in OPEN_MAPS else "maze"


def resolve_path(path):
    if os.path.isabs(path):
        return path
    return os.path.join(ROOT, path.replace("\\", os.sep).replace("/", os.sep))


def bounded_sample(sample, item, seen, limit, rng):
    """Reservoir-sample paths so input order does not decide the selected games."""
    seen += 1
    if len(sample) < limit:
        sample.append(item)
    else:
        j = rng.randrange(seen)
        if j < limit:
            sample[j] = item
    return seen


def collect_our(n, rng):
    samples = {"our wins": [], "our losses": []}
    seen = Counter()
    roots = [os.path.join(ROOT, "ladder", "attrib"),
             os.path.join(ROOT, "ladder", "losses")]
    # A replay may occur in both attribution and loss archives.
    used = set()
    for base in roots:
        for folder, dirs, files in os.walk(base):
            dirs.sort()
            for filename in sorted(files):
                if not filename.endswith(".replay"):
                    continue
                path = os.path.join(folder, filename)
                key = os.path.normcase(filename)
                if key in used:
                    continue
                used.add(key)
                try:
                    rep = _decode(path)
                    has_a, has_b = bool(rep.get("botA")), bool(rep.get("botB"))
                    if has_a == has_b:
                        continue
                    side = 0 if has_a else 1
                    winner = rep.get("result", {}).get("winner")
                    if winner not in (0, 1):
                        continue
                    group = "our wins" if winner == side else "our losses"
                    seen[group] = bounded_sample(samples[group], (path, side), seen[group], n, rng)
                except (OSError, ValueError, IndexError, KeyError, TypeError, EOFError):
                    continue
    return samples


def collect_top(n, rng):
    samples = {"top wins": [], "top losses": []}
    seen = Counter()
    index = os.path.join(ROOT, "ladder", "slope", "index.json")
    with open(index, encoding="utf-8") as f:
        entries = json.load(f)
    for row in entries:
        try:
            if int(row.get("rank", 999999)) > 6:
                continue
            side = 0 if row.get("side") == "A" else 1 if row.get("side") == "B" else None
            winner = 0 if row.get("winner") == "A" else 1 if row.get("winner") == "B" else None
            if side is None or winner is None or not row.get("path"):
                continue
            group = "top wins" if winner == side else "top losses"
            seen[group] = bounded_sample(samples[group], (resolve_path(row["path"]), side),
                                         seen[group], n, rng)
        except (TypeError, ValueError):
            continue
    return samples


def initial_state(map_text):
    teams, bodies = {}, {}
    width = height = None
    next_id = 0
    for line in map_text.splitlines():
        p = line.split()
        if p and p[0] == "MAP" and len(p) >= 3:
            try:
                width, height = int(p[1]), int(p[2])
            except ValueError:
                pass
        if p and p[0] == "DRAGON" and len(p) >= 3:
            team, length = int(p[1]), int(p[2])
            coords = [int(v) for v in p[3:3 + 2 * length]]
            bodies[next_id] = [(coords[i], coords[i + 1])
                               for i in range(0, len(coords) - 1, 2)]
            teams[next_id] = team
            next_id += 1
    return teams, bodies, width, height


def moved_cells(body, dirs, width, height):
    """Approximate ordinary wrapped steps; portals may make contact unresolvable."""
    if not body or width is None or height is None:
        return []
    x, y = body[0]
    out = []
    delta = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
    for d in dirs:
        dx, dy = delta[d]
        x, y = (x + dx) % width, (y + dy) % height
        out.append((x, y))
    return out


def contact_team(reason, dragon_id, cells, teams, bodies, alive, action_cells,
                  focus_side):
    """Return ally/enemy/unknown based on the other dragon's team."""
    candidates = []
    if reason == "hit other body":
        for cell in cells:
            for other in alive:
                if other != dragon_id and cell in bodies.get(other, ()):
                    candidates.append(other)
            if candidates:
                break
    else:  # head-to-head: shared destination or destination into the other head
        my_head = bodies.get(dragon_id, [None])[0]
        my_cells = set(cells)
        for other in alive:
            if other == dragon_id:
                continue
            other_body = bodies.get(other, ())
            other_head = other_body[0] if other_body else None
            other_cells = action_cells.get(other, ())
            if (other_head in my_cells or my_head in other_cells or
                    my_cells.intersection(other_cells)):
                candidates.append(other)
    if candidates:
        other = candidates[0]
        return "ally" if teams.get(other) == focus_side else "enemy"
    return "unknown"


def bucket(length):
    for lo, hi, label in BUCKETS:
        if lo <= length <= hi:
            return label
    return "other"


def phase(round_no):
    for i, (lo, hi) in enumerate(PHASES):
        if lo <= round_no < hi:
            return f"{lo}-{hi}"
    return None


def analyse(path, focus_side):
    rep = _decode(path)
    name = map_name(rep.get("map", ""))
    teams, bodies, width, height = initial_state(rep.get("map", ""))
    alive = set(teams)
    round_no = 0
    snapshots = {}
    death_counts = Counter()
    action_cells = {}
    pending_head_death = None

    def take_snapshot(r):
        dragons = [i for i in alive if teams.get(i) == focus_side]
        lengths = [len(bodies.get(i, ())) for i in dragons]
        snapshots[r] = (len(dragons), sum(lengths), max(lengths, default=0))

    for event in rep.get("events", ()):
        kind = event.get("kind")
        if kind == "roundStart":
            round_no = event.get("round", round_no)
            pending_head_death = None
            if round_no in CHECKPOINTS:
                take_snapshot(round_no)
        elif kind == "dragonAction":
            i = event.get("id")
            action_cells[i] = moved_cells(bodies.get(i, ()), event.get("dirs", ""), width, height)
        elif kind == "dragonUpdate":
            i, head, tail = event.get("id"), event.get("head"), event.get("tail")
            body = bodies.get(i)
            if body is not None and head is not None:
                if not body or body[0] != head:
                    body.insert(0, head)
                while len(body) > 1 and body[-1] != tail:
                    body.pop()
        elif kind == "dragonSplit":
            child, parent = event.get("child"), event.get("parent")
            teams[child] = event.get("team")
            bodies[child] = event.get("childBody") or []
            bodies[parent] = event.get("parentBody") or bodies.get(parent, [])
            alive.add(child)
        elif kind == "dragonDeath":
            i = event.get("id")
            if i not in alive:
                continue
            rid = event.get("reason", -1)
            reason = DEATHS[rid] if isinstance(rid, int) and 0 <= rid < len(DEATHS) else "unknown"
            length = len(bodies.get(i, ()))
            cause = reason
            if reason in CONTACT_CAUSES:
                if reason == "head to head" and pending_head_death:
                    other, prior_key = pending_head_death
                    relation = "ally" if teams.get(other) == focus_side else "enemy"
                    if prior_key is not None:
                        death_counts[prior_key] -= 1
                        death_counts[(prior_key[0], prior_key[1], "head to head " +
                                      ("ally" if teams.get(i) == focus_side else "enemy"))] += 1
                    pending_head_death = None
                else:
                    relation = contact_team(reason, i, action_cells.get(i, ()), teams,
                                            bodies, alive, action_cells, focus_side)
                cause = f"{reason} {relation}"
            if teams.get(i) == focus_side:
                ph = phase(round_no)
                if ph:
                    death_counts[(ph, bucket(length), cause)] += 1
                    if reason == "head to head" and cause.endswith("unknown"):
                        pending_head_death = (i, (ph, bucket(length), cause))
            elif reason == "head to head" and cause.endswith("unknown"):
                pending_head_death = (i, None)
            alive.discard(i)
            action_cells.pop(i, None)

    return {"map": name, "class": map_class(name), "snapshots": snapshots,
            "deaths": death_counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=25, help="games sampled per group (default: 25)")
    args = parser.parse_args()
    if args.n < 1:
        parser.error("--n must be at least 1")
    rng = random.Random(1)
    groups = collect_our(args.n, rng)
    groups.update(collect_top(args.n, rng))
    results = defaultdict(list)
    errors = []
    for group, games in groups.items():
        for path, side in games:
            try:
                result = analyse(path, side)
                results[(group, result["class"])].append(result)
            except (OSError, ValueError, IndexError, KeyError, TypeError, EOFError) as exc:
                errors.append(f"{path}: {exc}")

    print(f"Replay forensics; requested n={args.n} per group; top teams rank <= 6; sample seed=1")
    print("Focus side only. Trajectory values are medians across games; deaths are total and mean/game.")
    print("Contact ally/enemy means the other dragon shared/did not share the focus team's side; unknown means unresolved.\n")
    print("TRAJECTORIES: group | class | games | round | median units | median mass | median longest")
    for group in ("our wins", "our losses", "top wins", "top losses"):
        for cls in ("open", "maze"):
            games = results[(group, cls)]
            for r in CHECKPOINTS:
                rows = [g["snapshots"].get(r) for g in games if r in g["snapshots"]]
                if rows:
                    med = [statistics.median(row[k] for row in rows) for k in range(3)]
                    print(f"{group:10} {cls:4} {len(games):5} r{r:<3} {med[0]:12.1f} {med[1]:12.1f} {med[2]:14.1f}")
                else:
                    print(f"{group:10} {cls:4} {len(games):5} r{r:<3} {'-':>12} {'-':>12} {'-':>14}")

    print("\nDEATHS: group | class | phase | length | cause | total | per game")
    for group in ("our wins", "our losses", "top wins", "top losses"):
        for cls in ("open", "maze"):
            games = results[(group, cls)]
            denom = len(games)
            for ph in ("0-100", "100-300", "300-500"):
                for length_label in ("2-3", "4-6", "7+", "other"):
                    for cause in CAUSES:
                        count = sum(g["deaths"][(ph, length_label, cause)] for g in games)
                        print(f"{group:10} {cls:4} {ph:9} {length_label:6} {cause:24} {count:6d} {count / denom if denom else 0:8.3f}")

    print("\nGames used: " + ", ".join(
        f"{g}={sum(len(results[(g, c)]) for c in ('open', 'maze'))}" for g in
        ("our wins", "our losses", "top wins", "top losses")))
    if errors:
        print(f"Unreadable replays: {len(errors)}")
        for error in errors[:20]:
            print(error)


if __name__ == "__main__":
    main()
