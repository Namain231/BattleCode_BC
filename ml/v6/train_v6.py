"""Streaming trainer for the v6 imitation net (19 planes + 6 scalars -> 7 logits).

    python ml/v6/train_v6.py --data ladder/scout_v6/shards --out ladder/scout_v6/train_out/v6.pt [--epochs 8]

Shards are visited one at a time (never everything in RAM). Hold-out is by GAME (stable hash, ml/v6/build_dataset_v6.py
game_holdout). Per-sample weights come from the shards (queen samples x3). Left/right mirror augmentation with the
labels swapped. Resumable: a checkpoint is written atomically after each epoch and picked up with --resume.
The model class is ml/train.py's Policy, so ml/export_cpp.py exports it unchanged (NN_NPLANES/NN_NSCAL/NN_NOUT macros).
"""
import argparse, glob, json, os, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
from train import Policy          # noqa: E402
from build_dataset_v6 import game_holdout, LABELS, META  # noqa: E402

MIRROR_PLANES = [0, 3, 2, 1, 4, 7, 6, 5] + list(range(8, 19))   # swap left/right kelp + portal planes
MIRROR_LABELS = [0, 3, 2, 1, 4, 5, 6]
QUEEN = META.index("is_queen")


def shard_iter(files, order, batch, dev, split, frac, seed, rng, teams=None, only=None):
    """Yield (x, s, y, w, meta) batches for split in {'train','val'} from shards in the given order."""
    for k in order:
        z = np.load(files[k])
        g = z["game"]; hold = game_holdout(g, frac, seed)
        sel = np.where(hold if split == "val" else ~hold)[0]
        if only:
            sel = sel[np.isin(z["meta"][sel, 1], only)]
        if len(sel) == 0:
            continue
        if split == "train":
            sel = rng.permutation(sel)
        P, S, Y, W, M = z["planes"], z["scalars"], z["labels"], z["weights"], z["meta"]
        if teams:   # team conditioning: one-hot of the demonstrating team (top-N ids) + an "other" column
            oh = np.zeros((len(S), len(teams) + 1), np.float32)
            for k, t in enumerate(teams):
                oh[M[:, 1] == t, k] = 1
            oh[~np.isin(M[:, 1], teams), len(teams)] = 1
            S = np.concatenate([S, oh], 1)
        for i in range(0, len(sel), batch):
            ix = np.sort(sel[i:i + batch])
            yield (torch.from_numpy(P[ix]).to(dev).float() / 255, torch.from_numpy(S[ix]).to(dev),
                   torch.from_numpy(Y[ix].astype(np.int64)).to(dev), torch.from_numpy(W[ix]).to(dev), M[ix])


def evaluate(model, files, dev, batch, frac, seed, teams=None, only=None):
    model.eval(); n = 0; correct = 0; per = np.zeros((7, 2)); q = np.zeros(2); per_team = {}
    with torch.no_grad():
        for x, s, y, w, m in shard_iter(files, range(len(files)), batch, dev, "val", frac, seed, None, teams, only):
            pred = model(x, s).argmax(1); ok = (pred == y).cpu().numpy(); yy = y.cpu().numpy()
            n += len(yy); correct += int(ok.sum())
            for c in range(7):
                mk = yy == c; per[c] += [ok[mk].sum(), mk.sum()]
            iq = m[:, QUEEN] == 1; q += [ok[iq].sum(), iq.sum()]
            for t in np.unique(m[:, 1]):
                mk = m[:, 1] == t; a = per_team.setdefault(int(t), [0, 0]); a[0] += int(ok[mk].sum()); a[1] += int(mk.sum())
    model.train()
    return {"val_samples": n, "val_acc": correct / max(1, n),
            "per_class": {LABELS[c]: round(per[c, 0] / per[c, 1], 3) for c in range(7) if per[c, 1]},
            "queen_acc": round(q[0] / q[1], 3) if q[1] else None, "queen_n": int(q[1]),
            "per_team_acc": {t: round(a[0] / a[1], 3) for t, a in per_team.items() if a[1]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="ladder/scout_v6/shards"); ap.add_argument("--out", default="ladder/scout_v6/train_out/v6.pt")
    ap.add_argument("--epochs", type=int, default=8); ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=2e-3); ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--channels", type=int, default=32); ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-shards", type=int, default=0); ap.add_argument("--amp", action="store_true")
    ap.add_argument("--init", default="", help="warm start: state_dict from a previous v6 .pt (same architecture)")
    ap.add_argument("--team-cond", type=int, default=0, help="append a one-hot of the N most frequent demonstrating teams (+other) to the scalars")
    ap.add_argument("--only-teams", default="", help="comma separated team ids: train/validate only on these teams")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    files = sorted(glob.glob(os.path.join(a.data, "shard_*.npz")))
    if a.max_shards:
        files = files[:a.max_shards]
    assert files, "no shards"
    torch.manual_seed(a.seed); rng = np.random.default_rng(a.seed)
    only = [int(t) for t in a.only_teams.split(",") if t] or None
    teams = None
    if a.team_cond:
        cnt = {}
        for f in files:
            m = np.load(f)["meta"][:, 1]
            for t, c in zip(*np.unique(m[m >= 0], return_counts=True)):
                cnt[int(t)] = cnt.get(int(t), 0) + int(c)
        teams = [t for t, _ in sorted(cnt.items(), key=lambda kv: -kv[1])[:a.team_cond]]
        print("team conditioning on", teams, flush=True)
    nsc = 6 + (len(teams) + 1 if teams else 0)
    model = Policy(planes=19, scalars=nsc, ch=a.channels, hidden=a.hidden, classes=7).to(dev)
    if a.init:
        st0 = torch.load(a.init, map_location="cpu"); model.load_state_dict(st0["state_dict"] if "state_dict" in st0 else st0); print("warm start from", a.init, flush=True)
    # the zeroed plane 8 must stay at its initial range: freeze its input weights at zero-grad by masking the gradient
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    # total steps estimate from shard sizes (train games only)
    total = sum(int((~game_holdout(np.load(f)["game"], a.val_frac, a.seed)).sum()) for f in files)  # upper bound (only-teams may filter)
    steps = a.epochs * (total // a.batch + len(files) + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=steps)
    scaler = torch.amp.GradScaler(enabled=bool(a.amp and dev == "cuda"))
    mp = torch.tensor(MIRROR_PLANES, device=dev); my = torch.tensor(MIRROR_LABELS, device=dev)
    start = 0; out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    ck = out.with_suffix(".ckpt")
    if a.resume and ck.exists():
        st = torch.load(ck, map_location="cpu"); model.load_state_dict(st["model"]); opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"]); start = st["epoch"]; print("resumed at epoch", start)
    print(f"{len(files)} shards, {total} train samples, device {dev}, params {sum(p.numel() for p in model.parameters())}", flush=True)
    metrics = []
    for ep in range(start, a.epochs):
        t0 = time.time(); tot = 0.0; cnt = 0
        order = rng.permutation(len(files))
        for x, s, y, w, _ in shard_iter(files, order, a.batch, dev, "train", a.val_frac, a.seed, rng, teams, only):
            flip = torch.rand(len(y), device=dev) < 0.5
            if flip.any():
                x[flip] = x[flip][:, mp].flip(-1); y = torch.where(flip, my[y], y)
            with torch.autocast(device_type="cuda", enabled=bool(a.amp and dev == "cuda")):
                loss = (F.cross_entropy(model(x, s), y, reduction="none") * w).sum() / w.sum()
            opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            if sched.last_epoch < steps - 1:
                sched.step()
            tot += loss.item() * len(y); cnt += len(y)
        ev = evaluate(model, files, dev, a.batch, a.val_frac, a.seed, teams, only)
        ev.update(epoch=ep + 1, train_loss=tot / max(1, cnt), seconds=round(time.time() - t0), samples_per_s=round(cnt / max(1e-9, time.time() - t0)))
        metrics.append(ev); print(json.dumps(ev), flush=True)
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(), "epoch": ep + 1}, str(ck) + ".tmp")
        os.replace(str(ck) + ".tmp", ck)
    torch.save({"state_dict": model.state_dict(), "planes": 19, "scalars": nsc, "channels": a.channels, "hidden": a.hidden, "classes": 7, "teams": teams}, out)
    json.dump({"teams": teams, "scalars": nsc}, open(out.with_suffix(".teams.json"), "w"))
    json.dump(metrics, open(out.with_suffix(".metrics.json"), "w"), indent=1)
    print("saved", out)


if __name__ == "__main__":
    main()
