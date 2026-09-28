"""PPO fine-tuning of the imitation network by self-play in the in-process engine (ml/rl_env.py).

    python ml/rl_train.py --init ml/models/policy_v1b.pt --out ml/models/rl --workers 10 --games 10 --iters 200

Recipe (HandyRL for Kaggle Hungry Geese; AlphaStar's KL anchor to the supervised policy):
  - network: the imitation Policy with 12 outputs = 6 action logits + value head (output 6), initialised from --init
  - each iteration: --games self-play games in parallel worker processes; the learner plays one team, the other
    team is a frozen opponent drawn from a league (the imitation model + earlier snapshots)
  - reward per learner decision: final team result (+1 win / -1 loss) + 0.05 * that dragon's length gain over the
    next 20 rounds; value head as baseline (advantage = return - value)
  - PPO clipped objective + value loss + KL(imitation || current) penalty, on the GPU
Every --eval iterations: 10 greedy games vs the imitation model; snapshots and a log go to --out.
"""
import argparse
import copy
import glob
import multiprocessing as mp
import os
import random
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import Policy  # noqa: E402

MAPS = ["trophy", "queen_of_spades", "default", "dilemma", "autarky", "devil", "trauma", "portals",
        "slithery_fight", "schooltime"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = 0.3   # share of the learner's decisions kept per game (whole games do not fit in 15 GB with 10 workers)


def load_net(state, classes=12):
    net = Policy(scalars=3, classes=classes)
    net.load_state_dict(state)
    return net.eval()


class Sampler:
    """Masked sampling from a Policy state dict (CPU, batch 1)."""

    def __init__(self, state, greedy=False):
        self.net = load_net(state); self.greedy = greedy; self.rng = np.random.default_rng()

    @torch.no_grad()
    def __call__(self, pl, sc):
        from rl_policy import legal_mask
        out = self.net(torch.from_numpy(pl[None]).float() / 255, torch.from_numpy(sc[None]))[0]
        logits = out[:5].numpy(); value = float(out[6])
        m = legal_mask(pl, int(round(sc[0] * 32)))
        if not m.any():
            return 0, (0.0, m, value)
        logits = np.where(m, logits, -1e9)
        p = np.exp(logits - logits.max()); p /= p.sum()
        a = int(p.argmax()) if self.greedy else int(self.rng.choice(5, p=p))
        return a, (float(np.log(p[a] + 1e-12)), m, value)


def worker(args):
    learner_state, opp_state, map_name, seed, learner_team, greedy, team_coef = args
    torch.set_num_threads(1)
    from rl_env import play_game, team_potential
    learner = Sampler(learner_state, greedy)
    opp = Sampler(opp_state, greedy)
    pa, pb = (learner, opp) if learner_team == "A" else (opp, learner)
    # store only the learner's decisions, subsampled while playing (full games do not fit in RAM); none in eval games
    res, traj, lengths, splits, team_of = play_game(os.path.join(ROOT, "maps", f"{map_name}.map"), pa, pb,
                                                    seed=seed, record=() if greedy else (learner_team,), keep=KEEP)
    won = 1.0 if res.winner == learner_team else -1.0 if res.winner else 0.0
    keep = traj[learner_team]
    if not keep:
        return won, None, map_name
    phi = team_potential(lengths, team_of) if team_coef else {}
    sign = 1.0 if learner_team == "A" else -1.0
    last = max(phi) if phi else 0
    rets = []
    for pl, sc, act, (logp, mask, value), rnd, did in keep:
        h = lengths.get(did, {})
        later = [r for r in h if rnd < r <= rnd + 20]
        gain = (h[max(later)] - h.get(rnd, 0)) if later else -h.get(rnd, 0)   # died: lost its length
        # a split halves this dragon but creates a length-2 child: credit the child (else RL learns not to bud)
        gain += 2 * sum(1 for r in splits.get(did, []) if rnd <= r <= rnd + 20)
        ret = won + 0.05 * gain
        if phi and rnd in phi:
            # team standing 20 rounds later minus now (units and total length vs the enemy); at the end, the result
            end = phi[rnd + 20] if rnd + 20 in phi else won * sign if rnd + 20 > last else phi[rnd]
            ret += team_coef * sign * (end - phi[rnd])
        rets.append(ret)
    # compact arrays instead of a list of tuples: far less memory when sent back through the pool
    batch = (np.stack([t[0] for t in keep]), np.stack([t[1] for t in keep]),
             np.array([t[2] for t in keep], np.int64), np.array([t[3][0] for t in keep], np.float32),
             np.stack([t[3][1] for t in keep]), np.array([t[3][2] for t in keep], np.float32),
             np.array(rets, np.float32))
    return won, batch, map_name


def free_gb():
    """Free physical memory in GB (Windows; elsewhere assume plenty)."""
    if os.name != "nt":
        return 99.0
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + \
                   [(n, ctypes.c_ulonglong) for n in ("tot", "avail", "tpf", "apf", "tv", "av", "ax")]
    m = MS(); m.len = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def ppo_update(net, ref, batches, dev, epochs=2, batch=2048, clip=0.2, kl_coef=0.2, lr=1e-4, critic_only=False):
    """critic_only: train just the value output (row 6 of the last layer), policy frozen: the critic warm-up that
    avoids the drop-then-recover of PPO fine-tuning from an imitation policy with a fresh critic (PIRLNav)."""
    cat = [np.concatenate([b[k] for b in batches]) for k in range(7)]
    P, S, A, LP, M, V, R = (torch.from_numpy(x) for x in cat)
    rows = range(len(A))
    adv = R - V
    adv = (adv - adv.mean()) / (adv.std() + 1e-6)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    net.train(); stats = []
    for _ in range(epochs):
        perm = torch.randperm(len(rows))
        for i in range(0, len(rows), batch):
            ix = perm[i:i + batch]
            x = P[ix].to(dev).float() / 255; s = S[ix].to(dev)
            out = net(x, s)
            logits = out[:, :5].masked_fill(~M[ix].to(dev), -1e9)
            logp_all = F.log_softmax(logits, 1)
            logp = logp_all.gather(1, A[ix].to(dev)[:, None])[:, 0]
            ratio = torch.exp(logp - LP[ix].to(dev))
            a = adv[ix].to(dev)
            pg = -torch.min(ratio * a, torch.clamp(ratio, 1 - clip, 1 + clip) * a).mean()
            vloss = F.mse_loss(out[:, 6], R[ix].to(dev))
            with torch.no_grad():
                ref_logits = ref(x, s)[:, :5].masked_fill(~M[ix].to(dev), -1e9)
                ref_logp = F.log_softmax(ref_logits, 1)
            kl = (ref_logp.exp() * (ref_logp - logp_all)).sum(1).mean()
            loss = vloss if critic_only else pg + 0.5 * vloss + kl_coef * kl
            opt.zero_grad(); loss.backward()
            if critic_only:
                for name, p in net.named_parameters():
                    if not name.startswith("out."):
                        p.grad = None
                    else:
                        keep = torch.zeros_like(p.grad); keep[6] = p.grad[6]; p.grad = keep
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
            stats.append((pg.item(), vloss.item(), kl.item()))
    net.eval()
    return np.mean(stats, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", default="ml/models/policy_v1b.pt")
    ap.add_argument("--out", default="ml/models/rl")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--eval", type=int, default=5)
    ap.add_argument("--resume", default="", help="snapshot rl_NNNN.pt to continue from (iteration NNNN+1)")
    ap.add_argument("--min-free-gb", type=float, default=3.0, help="pause before an iteration below this much free RAM")
    ap.add_argument("--team-coef", type=float, default=0.0,
                    help="weight of the team-standing reward (units and total length vs the enemy, 20 rounds ahead)")
    ap.add_argument("--eval-games", type=int, default=10, help="eval games per snapshot (a multiple of 10)")
    ap.add_argument("--kl", type=float, default=0.2, help="KL(imitation || current) penalty weight")
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--critic-warmup", type=int, default=0, help="iterations training only the value head first")
    ap.add_argument("--lr-ramp", type=int, default=1, help="iterations to ramp the policy lr in after the warm-up")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    os.makedirs(a.out, exist_ok=True)
    init = torch.load(a.init, map_location="cpu")
    # 12-output network: copy the imitation trunk and action head; value head starts at zero
    net = Policy(scalars=3, classes=12)
    sd = net.state_dict()
    for k, v in init["state_dict"].items():
        if k.startswith("out."):
            sd[k][:v.shape[0]] = v
        else:
            sd[k] = v
    net.load_state_dict(sd); net.to(dev).eval()
    ref = copy.deepcopy(net).eval()                     # the imitation policy: KL anchor
    league = [{k: v.cpu().clone() for k, v in net.state_dict().items()}]
    start = 1
    if a.resume:                                        # continue from a snapshot; --init stays the KL anchor
        ck = torch.load(a.resume, map_location="cpu")
        net.load_state_dict(ck["state_dict"]); net.to(dev).eval()
        league.append({k: v.cpu().clone() for k, v in ck["state_dict"].items()})
        start = int(os.path.basename(a.resume)[3:7]) + 1
    log = open(os.path.join(a.out, "log.txt"), "a")
    pool = mp.Pool(a.workers)
    for it in range(start, a.iters + 1):
        while free_gb() < a.min_free_gb:                # leave room for the rest of the laptop
            print(f"  waiting: only {free_gb():.1f} GB free", flush=True); time.sleep(60)
        t0 = time.time()
        state = {k: v.cpu().clone() for k, v in net.state_dict().items()}
        # opponents: half the games the imitation model, else one of the 3 latest snapshots (generals.io pool)
        opps = [league[0] if random.random() < 0.5 else random.choice(league[-3:]) for _ in range(a.games)]
        jobs = [(state, o, random.choice(MAPS), random.randrange(1 << 30), random.choice("AB"), False, a.team_coef)
                for o in opps]
        results = pool.map(worker, jobs)
        batches = [b for _, b, _ in results if b is not None]
        wins = [w for w, _, _ in results]
        warm = it <= a.critic_warmup
        # after the critic warm-up, ramp the policy learning rate in linearly over --lr-ramp iterations
        lr = 1e-3 if warm else a.lr * min(1.0, (it - a.critic_warmup) / max(1, a.lr_ramp))
        pg, vl, kl = ppo_update(net, ref, batches, dev, kl_coef=a.kl, lr=lr, critic_only=warm)
        msg = (f"iter {it}: {sum(len(b[2]) for b in batches)} decisions, learner vs league {np.mean([w > 0 for w in wins]):.2f} "
               f"(ties {np.mean([w == 0 for w in wins]):.2f}), pg {pg:+.3f} v {vl:.3f} kl {kl:.4f} [{time.time() - t0:.0f}s]")
        print(msg, flush=True); log.write(msg + "\n"); log.flush()
        if it % a.eval == 0:
            state = {k: v.cpu().clone() for k, v in net.state_dict().items()}
            league.append(state)
            torch.save({"state_dict": net.state_dict(), "planes": 16, "scalars": 3, "channels": 32, "hidden": 64,
                        "classes": 12, "kind": "rl"}, os.path.join(a.out, f"rl_{it:04d}.pt"))
            # greedy vs the imitation model: each map once (sides alternate), twice with sides swapped for 20 games
            ev = pool.map(worker, [(state, league[0], m, 7 + k + 100 * rep, "AB"[(k + rep) % 2], True, 0)
                                   for rep in range(a.eval_games // len(MAPS)) for k, m in enumerate(MAPS)])
            wr = np.mean([w > 0 for w, _, _ in ev])
            msg = f"  eval iter {it}: greedy vs imitation model {wr:.2f} ({' '.join(m[:5] + ('W' if w > 0 else 'L') for w, _, m in ev)})"
            print(msg, flush=True); log.write(msg + "\n"); log.flush()


if __name__ == "__main__":
    main()
