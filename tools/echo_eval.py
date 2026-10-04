"""Offline sonar evaluation on real replays; CLI unchanged.

Counterfactual casts use post-action state, and echoes become usable next turn.
Known whole-map terrain and the common truth-distance FAR mask are upper bounds,
not deployable unknown-map observations. No files are written by this script.
"""
import argparse
import bisect
import collections
import itertools
import json
import random
import sys
from pathlib import Path
from typing import NamedTuple

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_lite import decode_lite
from engine_sim import load_map

DIRS = "NESW"
KINDS = ("kelp", "ally", "ally_head", "enemy", "enemy_head", "none")
HOT = {"enemy", "enemy_head"}
VIEW, FAR, HORIZON = 3, 12, 5
REPETITIONS = 200


class Hit(NamedTuple):
    kind: str
    steps: int
    cell: object
    dragon: object
    portal: bool
    refracted: bool


def portal_edges(text, board):
    """Mark actual portal edges, including portals with adjacent destinations."""
    result = set()
    for line in text.splitlines():
        p = line.split()
        if p and p[0] == "EDGE" and int(p[2]) == 2:
            row, col = divmod(int(p[1]), board.width + 1)
            o, x, y = row % 2, col % board.width, (row // 2) % board.height
            if o == 0:
                result.update({((x, y), 0), ((x, (y - 1) % board.height), 2)})
            else:
                result.update({((x, y), 3), (((x - 1) % board.width, y), 1)})
    return result


def ray(board, occ, head, d, own, team, body, limit, facing=None, portals=frozenset()):
    """Engine CastSonar: backward ray starts at tail; subsequent own hits stop."""
    if facing is None:
        facing = board.facing(body[1], head) if len(body) > 1 else -1
    refracted = len(body) > 1 and d == (facing + 2) % 4
    cur = body[-1] if refracted else head
    if refracted:
        along = board.facing(body[-2], body[-1])
        if along >= 0:
            d = along
    portal = False
    for step in range(limit):
        nxt = board.neighbours[cur, d]
        if nxt is None:
            return Hit("kelp", step, cur, None, portal, refracted)
        portal |= (cur, d) in portals
        cur = nxt
        o = occ.get(cur)
        if o is not None:
            i, idx, t = o
            kind = ("ally" if t == team else "enemy") + ("_head" if idx == 0 else "")
            return Hit(kind, step + 1, cur, i, portal, refracted)
    return Hit("none", limit, cur, None, portal, refracted)


def visible(hit):
    # Tail-emitted rays are not straight rays from the queen's head.
    return hit.kind != "none" and hit.steps <= VIEW and not hit.portal and not hit.refracted


def lane_of(f, d):
    return (d - f) % 4


def reachability(board, occ, body, alive, teams, facing, qid, portals):
    friends = set(i for i in alive if teams[i] == teams[qid] and i != qid)
    graph = {}
    enemy = False
    limit = board.width + board.height
    for i in alive:
        if i == qid:
            continue
        targets = set()
        for d in range(4):
            hit = ray(board, occ, body[i][0], d, i, teams[i], body[i], limit,
                      facing.get(i), portals)
            if hit.dragon is not None:
                targets.add(hit.dragon)
        if i in friends:
            graph[i] = targets & (friends | {qid})
        else:
            enemy |= qid in targets
    reached = {qid}
    hops = []
    for _ in range(3):
        reached |= {i for i in friends if graph[i] & reached}
        hops.append(bool(reached & friends))
    direct = sum(qid in graph[i] for i in friends)
    qx, qy = body[qid][0]
    near = any(max(min(abs(body[i][0][0] - qx), board.width - abs(body[i][0][0] - qx)),
                       min(abs(body[i][0][1] - qy), board.height - abs(body[i][0][1] - qy))) <= 8
               for i in friends)
    return dict(direct=direct, hop2=hops[1], hop3=hops[2], friends=len(friends),
                enemy=enemy, near=near)


def decode_game(path, me):
    rep = decode_lite(str(path), {"roundStart", "turnStart", "dragonAction",
                                 "dragonUpdate", "dragonSplit", "dragonDeath", "sonarPing"})
    st = load_map(rep["map"], 1)
    board = st.board
    portals = portal_edges(rep["map"], board)
    limit = board.width + board.height
    teams = {i: d.team for i, d in st.dragons.items()}
    body = {i: list(d.body) for i, d in st.dragons.items()}
    facing = {i: d.facing for i, d in st.dragons.items()}
    alive = set(body)
    qid = next(i for i in (0, 1) if teams.get(i) == me)
    pending, updates = {}, collections.Counter()
    rnd, actor, last_q = -1, None, None
    turns, qdeath = [], None
    validation = collections.Counter()
    samples = []

    def occ_map():
        return {c: (i, j, teams[i]) for i in sorted(alive)
                for j, c in enumerate(body[i])}

    def finish_queen():
        nonlocal last_q
        if last_q is not None and qid in alive:
            o = occ_map()
            b = body[qid]
            truth = [ray(board, o, b[0], d, qid, me, b, limit, facing[qid], portals)
                     for d in range(4)]
            # Empty occupancy, not actual obstacle, determines terrain eligibility.
            base = [ray(board, {}, b[0], d, qid, me, b, limit, facing[qid], portals).kind
                    for d in range(4)]
            # Baseline sees the square occupancy directly, including cells
            # beyond kelp edges; it does not use synthetic sonar obstacles.
            hx, hy = b[0]
            view_enemy = []
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                view_enemy.append(any(
                    o.get(((hx + dx * step) % board.width,
                           (hy + dy * step) % board.height), (None, None, me))[2] != me
                    for step in range(1, VIEW + 1)))
            t = dict(round=last_q, facing=facing[qid], truth=truth, base=base,
                     view_enemy=view_enemy,
                     reach=reachability(board, o, body, alive, teams, facing, qid, portals))
            if turns and turns[-1]["round"] == last_q:
                turns[-1] = t
            else:
                turns.append(t)
        last_q = None

    for e in rep["events"]:
        k = e["kind"]
        if k == "roundStart":
            finish_queen()
            rnd = e["round"]
        elif k == "turnStart":
            finish_queen()
            actor = e["id"]
            if actor == qid and rnd >= 0:
                last_q = rnd
            updates[actor] = 0
            pending.pop(actor, None)
        elif k == "dragonAction":
            actor = e["id"]
            pending[actor] = list(e.get("dirs", "")) if e.get("act") == "move" else []
        elif k == "dragonUpdate":
            i = e["id"]
            if i not in body:
                continue
            b, head = body[i], e["head"]
            dirs = pending.get(i, [])
            if head is not None and head != b[0]:
                # One replay update per successful sprint step. Consume only its
                # prefix; do not insert the entire requested path repeatedly.
                cur, path, used = b[0], [], 0
                for ch in dirs:
                    cur = board.neighbours[cur, DIRS.index(ch)]
                    used += 1
                    if cur is None:
                        break
                    path.append(cur)
                    if cur == head:
                        break
                if path and path[-1] == head:
                    for c in path:
                        b.insert(0, c)
                    pending[i] = dirs[used:]
                else:
                    validation["movement_fallback"] += 1
                    b.insert(0, head)
            while len(b) > 1 and b[-1] != e["tail"]:
                b.pop()
            if b[-1] != e["tail"]:
                raise ValueError(f"tail reconstruction failed for dragon {i} round {rnd}")
            facing[i] = e["facing"] % 4
            updates[i] += 1
            if i == qid and actor == qid and rnd >= 0:
                last_q = rnd
        elif k == "dragonSplit":
            teams[e["child"]] = e["team"]
            body[e["child"]] = list(e["childBody"])
            body[e["parent"]] = list(e["parentBody"])
            facing[e["child"]] = board.facing(body[e["child"]][1], body[e["child"]][0])
            alive.add(e["child"])
        elif k == "dragonDeath":
            alive.discard(e["id"])
            if e["id"] == qid:
                qdeath = (rnd, e["reason"])
        elif k == "sonarPing" and e.get("sender") in alive:
            s = e["sender"]
            # Replay dir is the outgoing direction after tail refraction,
            # not necessarily the requested cardinal lane. Origin disambiguates.
            requested = ((facing[s] + 2) % 4 if e.get("origin") == body[s][-1]
                         and body[s][-1] != body[s][0] else DIRS.index(e["dir"]))
            hit = ray(board, occ_map(), body[s][0], requested, s,
                      teams[s], body[s], limit, facing[s], portals)
            expected_kind = "none" if e["hitKind"] == "empty" else e["hitKind"]
            checks = (hit.cell == e.get("end"), hit.kind == expected_kind,
                      hit.dragon == e.get("hit"))
            validation["n"] += 1
            for label, ok in zip(("endpoint", "kind", "dragon"), checks):
                validation[label] += ok
            validation["all"] += all(checks)
            if not all(checks):
                category = ("portal" if hit.portal else "own-body refraction" if hit.refracted
                            else "sprint-reconstruction" if updates[s] > 1 else "other")
                validation[category] += 1
                if len(samples) < 5:
                    samples.append((rnd, s, e["dir"], tuple(hit), e.get("end"),
                                    expected_kind, e.get("hit")))
    finish_queen()
    assert len(turns) == len({t["round"] for t in turns})
    assert len(turns) <= rnd + 1
    return turns, qdeath, validation, samples, rnd + 1


def fit_prior(games):
    counts = collections.defaultdict(collections.Counter)
    for gm in games:
        for t in gm["turns"]:
            for d, hit in enumerate(t["truth"]):
                if not visible(hit):
                    counts[t["base"][d]][hit.kind] += 1
    priors = {}
    for base in ("kelp", "none"):
        allowed = (base, "ally", "ally_head", "enemy", "enemy_head")
        total = sum(counts[base][k] for k in allowed)
        # Laplace smoothing, conditional on terrain-only base, gives a coherent
        # base-vs-dragon distribution instead of an arbitrary base weight of 1.
        priors[base] = {k: (counts[base][k] + 1) / (total + len(allowed)) for k in allowed}
    return priors, {b: dict(c) for b, c in counts.items()}


def posterior(cast, truth, base, prior):
    counts = collections.Counter(truth[d].kind for d in cast if truth[d].kind != "none")
    unresolved = []
    result = {}
    for d in cast:
        if visible(truth[d]):
            counts[truth[d].kind] -= 1
            result[d] = float(truth[d].kind in HOT)
        else:
            unresolved.append(d)
    weight, hot = 0.0, collections.Counter()
    opts = [list(prior[base[d]].items()) for d in unresolved]
    wanted = tuple(counts[k] for k in KINDS[:5])
    for combo in itertools.product(*opts):
        c = collections.Counter(k for k, _ in combo if k != "none")
        if tuple(c[k] for k in KINDS[:5]) != wanted:
            continue
        w = 1.0
        for _, p in combo:
            w *= p
        weight += w
        for d, (k, _) in zip(unresolved, combo):
            if k in HOT:
                hot[d] += w
    if unresolved and weight == 0:
        raise ValueError("impossible echo counts: terrain/ray reconstruction inconsistent")
    result.update({d: hot[d] / weight for d in unresolved})
    return result


POLICIES = ("all4", "three", "fwd1", "alt2", "adapt2", "fwd_rot", "fwd_left",
            "fwd_right", "three_nofwd_stale")


def cast_policy(name, t, state):
    f = t["facing"]
    three = [f, (f + 1) % 4, (f + 3) % 4]
    if name == "all4":
        return list(range(4))
    if name in ("three", "three_nofwd_stale"):
        return three
    if name == "fwd1":
        return [f]
    if name == "alt2":
        return [(f + 1) % 4, (f + 3) % 4] if t["round"] % 2 else [f, (f + 2) % 4]
    if name == "fwd_rot":
        return [f, (f + (1 if t["round"] % 2 else 3)) % 4]
    if name == "fwd_left":
        return [f, (f + 3) % 4]
    if name == "fwd_right":
        return [f, (f + 1) % 4]
    score = {d: state["belief"].get(d, 0.1) + 0.04 * (t["round"] - state["last"].get(d, -9))
             + (0.15 if d == f else 0) for d in three}
    return sorted(three, key=lambda d: -score[d])[:2]


def death_index(gm, headon_only=True):
    qd = gm["qdeath"]
    if qd is None or (headon_only and qd[1] != 3):
        return None
    # Death is a terminal record if her failed move emitted no alive update.
    # If another dragon kills her later in her cast round, that cast's echoes
    # cannot arrive before death. bisect_left excludes that same-round warning.
    return bisect.bisect_left([t["round"] for t in gm["turns"]], qd[0])


def warning_statistics(sequences):
    n = alarm = warned = deaths = false = yes = no = yes_event = no_event = 0
    eligible_shuffle = []
    excluded = 0
    for gm, warnings in sequences:
        dead = death_index(gm)
        n += len(warnings)
        alarm += sum(warnings)
        if dead is not None:
            deaths += 1
            warned += any(warnings[max(0, dead - HORIZON):dead])
        for i, warn in enumerate(warnings):
            event = dead is not None and 0 < dead - i <= HORIZON
            false += bool(warn and not event)
            # Remove right-censored precision observations at surviving game end.
            if gm["qdeath"] is None and i + HORIZON >= len(warnings):
                continue
            yes += bool(warn)
            no += not warn
            yes_event += bool(warn and event)
            no_event += bool(not warn and event)
        if dead is not None:
            if len(warnings) > 20:
                eligible_shuffle.append((dead, warnings))
            else:
                excluded += 1
    rng = random.Random(20261004)
    shuffled = []
    observed = sum(any(w[max(0, dead - HORIZON):dead]) for dead, w in eligible_shuffle)
    for _ in range(REPETITIONS):
        hits = 0
        for dead, warnings in eligible_shuffle:
            offset = rng.randint(20, len(warnings) - 1)
            hits += any(warnings[(i - offset) % len(warnings)]
                        for i in range(max(0, dead - HORIZON), dead))
        shuffled.append(hits)
    mean = sum(shuffled) / REPETITIONS
    ordered = sorted(shuffled)
    lo, hi = ordered[4], ordered[194]
    return dict(turns=n, alarms=alarm, warned=warned, deaths=deaths, false=false,
                p_warn=yes_event / max(1, yes), p_no=no_event / max(1, no),
                precision_n=(yes, no), shuffled=mean, shuffle_interval=(lo, hi),
                lift=observed / mean if mean else None,
                lift_interval=(observed / hi if hi else None, observed / lo if lo else None),
                shuffle_observed=observed, shuffle_excluded=excluded)


def evaluate(name, games, prior):
    totals = collections.Counter()
    sequences = []
    for gm in games:
        state = dict(belief={}, last={})
        pending = None
        warnings = []
        for t in gm["turns"]:
            # Adaptive selection can use only the previous turn's returned echoes.
            if pending is not None:
                post, previous_round = pending
                state["belief"].update(post)
                state["last"].update({d: previous_round for d in post})
            if name in ("oracle", "vision_only"):
                cast, post = (list(range(4)) if name == "oracle" else []), {}
            else:
                cast = cast_policy(name, t, state)
                post = posterior(cast, t["truth"], t["base"], prior)
                pending = (post, t["round"])
            totals["turns"] += 1
            totals["casts"] += len(cast)
            warn = False
            for d, hit in enumerate(t["truth"]):
                lane = lane_of(t["facing"], d)
                # All echo policies and oracle use identical non-back,
                # unresolved lanes and the same privileged <=FAR distance mask.
                eligible = lane != 2 and not visible(hit) and hit.steps <= FAR
                if eligible:
                    target = hit.kind in HOT
                    p = float(target) if name == "oracle" else post.get(d, 0.0)
                    totals["lanes"] += 1
                    totals["covered"] += d in cast
                    totals["brier_sum"] += (p - target) ** 2
                    totals["tp"] += bool(p > 0.5 and target)
                    totals["fp"] += bool(p > 0.5 and not target)
                    totals["fn"] += bool(p <= 0.5 and target)  # includes uncast misses
                    if name != "vision_only":
                        warn |= p > 0.5
                if name == "vision_only" and lane != 2:
                    warn |= t["view_enemy"][d]
            warnings.append(bool(warn))
        sequences.append((gm, warnings))
    return totals, sequences


def print_policy(name, totals, sequences):
    r = warning_statistics(sequences)
    t = totals
    lift = "NA" if r["lift"] is None else f'{r["lift"]:.2f}'
    def fmt(x):
        return "inf/NA" if x is None else f"{x:.2f}"
    print(f'{name} | {t["casts"]/max(1,t["turns"]):.2f} | '
          f'{t["covered"]/max(1,t["lanes"]):.3f} | {t["brier_sum"]/max(1,t["lanes"]):.3f} | '
          f'{t["tp"]/max(1,t["tp"]+t["fn"]):.3f} | {t["tp"]/max(1,t["tp"]+t["fp"]):.3f} | '
          f'{r["alarms"]/max(1,r["turns"]):.3f} | {100*r["false"]/max(1,r["turns"]):.2f} | '
          f'{r["warned"]}/{r["deaths"]} | {r["shuffled"]:.2f} '
          f'[{r["shuffle_interval"][0]},{r["shuffle_interval"][1]}] | {lift} '
          f'[{fmt(r["lift_interval"][0])},{fmt(r["lift_interval"][1])}] | '
          f'{r["p_warn"]:.4f} / {r["p_no"]:.4f} (n={r["precision_n"]})')
    if r["shuffle_excluded"]:
        print(f'  shuffle excluded {r["shuffle_excluded"]} deaths: 20 or fewer records')
    return r


def print_reach(data):
    groups = collections.defaultdict(list)
    map_counts = collections.Counter(g["map"] for g in data)
    top_maps = {m for m, _ in map_counts.most_common(10)}
    for gm in data:
        dead = death_index(gm)
        any_dead = death_index(gm, headon_only=False)
        for i, t in enumerate(gm["turns"]):
            r = t["reach"]
            groups["overall"].append(r)
            phase = "<100" if t["round"] < 100 else "100-299" if t["round"] < 300 else ">=300"
            groups["phase " + phase].append(r)
            if gm["map"] in top_maps:
                groups[f'map {gm["map"]} ({map_counts[gm["map"]]} games)'].append(r)
            if dead is not None and 0 < dead - i <= HORIZON:
                groups["head-on death window (5 records)"].append(r)
            if any_dead is not None and 0 < any_dead - i <= HORIZON:
                groups["all queen death windows (5 records)"].append(r)
    print("\nREACHABILITY: all alive dragons cast four hypothetical rays, no FAR cutoff.")
    print("group | records | direct fraction | mean hitting friends | 2 hops | 3 hops | "
          "mean alive friends | enemy direct | near8 records | near8 direct | near8 mean hitting friends | near8 2 hops | near8 3 hops")
    for group, rows in groups.items():
        near = [r for r in rows if r["near"]]
        def avg(rs, key, boolean=False):
            return sum(bool(r[key]) if boolean else r[key] for r in rs) / len(rs) if rs else float("nan")
        print(f'{group} | {len(rows)} | {avg(rows,"direct",True):.3f} | '
              f'{avg(rows,"direct"):.3f} | {avg(rows,"hop2"):.3f} | {avg(rows,"hop3"):.3f} | '
              f'{avg(rows,"friends"):.2f} | {avg(rows,"enemy"):.3f} | {len(near)} | '
              f'{avg(near,"direct",True):.3f} | {avg(near,"direct"):.3f} | '
              f'{avg(near,"hop2"):.3f} | {avg(near,"hop3"):.3f}')
    print("Any-friend 2/3-hop fractions equal direct reach by construction: the last "
          "friend on any path is itself a direct sender. Multi-hop can expand which friends "
          "reach her, but cannot create a record with no direct sender.")
    return groups["overall"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--max-games", type=int, default=30)
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    root = Path(a.dir)
    with (root / "games.json").open(encoding="utf-8") as f:
        games = json.load(f)[:a.max_games]
    data, validation, failures, samples = [], collections.Counter(), [], []
    for index, g in enumerate(games):
        try:
            turns, qd, val, examples, rounds = decode_game(root / f'{g["game"]}.replay', g["me"])
        except Exception as ex:
            failures.append((g["game"], type(ex).__name__, str(ex)))
            continue
        data.append(dict(game=g["game"], map=g["map"], index=index, turns=turns,
                         qdeath=qd, rounds=rounds))
        validation.update(val)
        samples.extend((g["game"], x) for x in examples[:2])
    if not data:
        raise RuntimeError(f"No games decoded: {failures}")
    folds, pooled = [], {}
    for test_parity in (0, 1):
        train = [g for g in data if g["index"] % 2 != test_parity]
        test = [g for g in data if g["index"] % 2 == test_parity]
        if not train or not test:
            raise ValueError("Both parity halves need at least one successfully decoded game")
        prior, counts = fit_prior(train)
        results = {}
        for name in (*POLICIES, "oracle", "vision_only"):
            totals, seq = evaluate(name, test, prior)
            results[name] = totals, seq
            if name not in pooled:
                pooled[name] = collections.Counter(), []
            pooled[name][0].update(totals)
            pooled[name][1].extend(seq)
        folds.append((test_parity, len(train), len(test), counts, prior, results))
    summary = warning_statistics(pooled["all4"][1])
    overall = [t["reach"] for g in data for t in g["turns"]]
    print("SUMMARY echo_eval_v2")
    print(f'{len(data)}/{len(games)} games decoded; {sum(len(g["turns"]) for g in data)} '
          f'unique queen records; failed games={len(failures)}.')
    print(f'Ray validation all fields: {validation["all"]}/{validation["n"]} '
          f'({validation["all"]/max(1,validation["n"]):.4%}); '
          f'all4 head-on deaths warned={summary["warned"]}/{summary["deaths"]}; '
          f'shuffled mean={summary["shuffled"]:.2f}, lift={summary["lift"]}.')
    print(f'Friend direct reach={sum(bool(r["direct"]) for r in overall)/max(1,len(overall)):.3%}; '
          f'2-hop={sum(r["hop2"] for r in overall)/max(1,len(overall)):.3%}; '
          f'3-hop={sum(r["hop3"] for r in overall)/max(1,len(overall)):.3%}.')
    print("Echo warnings formed at record i are usable only at records >i; "
          "terminal death index is the first queen record at/after death round.")
    print("Lane metrics: every unresolved non-back lane within FAR=12, including uncast misses. "
          "Truth-distance mask and known whole-map terrain are privileged upper bounds.")
    print("VISION-ONLY scans square-view occupancy on non-back cardinal lanes (no sonar), same 5-record horizon; "
          "same strict delayed warning convention. Echo policies warn on unseen lanes only; "
          "three_nofwd_stale explicitly excludes view-resolved lanes (no stale carryover).")
    print("Shuffle: 200 deterministic repetitions, positive offsets >=20 (modulo game length); "
          "brackets are empirical central 95% null counts and reciprocal lift intervals, "
          "not confidence intervals for causal benefit. Precision excludes surviving end censoring.")
    print("\nRAY VALIDATION")
    for label in ("endpoint", "kind", "dragon", "all"):
        print(f'{label}: {validation[label]}/{validation["n"]} = '
              f'{validation[label]/max(1,validation["n"]):.6f}')
    print("Mismatch classes (exclusive, portal then refraction then sprint then other):",
          {k: validation[k] for k in ("portal", "own-body refraction", "sprint-reconstruction", "other")})
    print("Movement fallback count:", validation["movement_fallback"])
    if a.validate or validation["all"] != validation["n"]:
        print("Mismatch examples:", samples[:10])
    print("\nRECORD COUNTS: game | map | queen records | rounds | queen death")
    for g in data:
        print(f'{g["game"]} | {g["map"]} | {len(g["turns"])} | {g["rounds"]} | {g["qdeath"]}')
    header = ("policy | rays/turn | lane coverage | Brier(all eligible lanes) | recall | precision | "
              "alarm rate | false/100 | deaths warned | shuffled mean [95%] | lift [95%] | "
              "P(death<=5|warn) / P(death<=5|no warn)")
    for parity, ntrain, ntest, counts, prior, results in folds:
        print(f"\nHELD-OUT FOLD: train parity {1-parity} ({ntrain} games), "
              f"evaluate parity {parity} ({ntest} games)")
        print("Training frequencies by terrain-only base:", counts)
        print("Smoothed training priors:", prior)
        print(header)
        for name, (totals, seq) in results.items():
            print_policy(name, totals, seq)
    print("\nPOOLED CROSS-FITTED RESULTS (each game evaluated with the opposite half's prior)")
    print(header)
    for name, (totals, seq) in pooled.items():
        print_policy(name, totals, seq)
    print("\nUNWEIGHTED TWO-FOLD MEAN: policy | Brier | recall | precision | alarm rate | death coverage")
    for name in (*POLICIES, "oracle", "vision_only"):
        rows = []
        for *_, results in folds:
            t, seq = results[name]
            r = warning_statistics(seq)
            rows.append((t["brier_sum"]/max(1,t["lanes"]), t["tp"]/max(1,t["tp"]+t["fn"]),
                         t["tp"]/max(1,t["tp"]+t["fp"]), r["alarms"]/max(1,r["turns"]),
                         r["warned"]/max(1,r["deaths"])))
        print(name, "|", " | ".join(f"{sum(v)/2:.4f}" for v in zip(*rows)))
    print_reach(data)
    print("\nFailed games:", failures)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
