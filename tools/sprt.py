"""Sequential Probability Ratio Test (SPRT) for bot comparison -- per
over-yonder.tech/games/loong/better-worse-or-undecided/'s writeup of the same idea (and the
standard technique chess-engine testing frameworks like cutechess-cli/fishtest use).

Every A/B test and param_search run this session played a fixed batch of games (16-32) and
eyeballed the win rate against an arbitrary min-gain threshold -- repeatedly caveated as "noisy,
small sample." SPRT instead tests two specific hypotheses about the candidate's true win rate
against a fixed opponent:

    H0 (p0): the candidate is no better than the baseline (e.g. p0 = 0.5, a coin flip)
    H1 (p1): the candidate is meaningfully better (e.g. p1 = 0.55, corresponding to a real gain)

and updates a log-likelihood ratio (LLR) after every game, stopping as soon as either hypothesis is
confident (crossing an upper/lower bound set by the desired false-positive/false-negative rates)
rather than always playing a fixed number of games. This is usually both faster (stops early on a
clear result) and more statistically honest than a fixed-batch-plus-threshold approach.

    from sprt import Sprt
    s = Sprt(p0=0.5, p1=0.6)
    for each game: s.update(won=True/False)  # draws: call update twice with won=True/False at 0.5 weight, or skip
    if s.decided: print(s.verdict)  # "accept" (candidate better), "reject" (no material difference)
"""
import argparse
import math


def llr_bounds(alpha=0.05, beta=0.05):
    """Standard Wald SPRT bounds for false-positive rate alpha, false-negative rate beta."""
    upper = math.log((1 - beta) / alpha)
    lower = math.log(beta / (1 - alpha))
    return lower, upper


class Sprt:
    def __init__(self, p0, p1, alpha=0.05, beta=0.05, max_games=400):
        assert 0 < p0 < 1 and 0 < p1 < 1 and p0 != p1
        self.p0, self.p1 = p0, p1
        self.lower, self.upper = llr_bounds(alpha, beta)
        self.max_games = max_games
        self.llr = 0.0
        self.n = 0
        self.wins = 0
        self.verdict = None  # None (undecided), "accept", "reject", "inconclusive" (hit max_games)

    def update(self, won: bool):
        """Call once per completed decisive game (skip draws, or split a draw into two 0.5-weight
        calls if you want draws to count as partial evidence -- kept simple here since this game's
        round-500 tiebreak makes true draws rare and not very informative either way)."""
        if self.verdict is not None:
            return self.verdict
        self.n += 1
        self.wins += 1 if won else 0
        # Bernoulli log-likelihood ratio increment for this single outcome.
        if won:
            self.llr += math.log(self.p1 / self.p0)
        else:
            self.llr += math.log((1 - self.p1) / (1 - self.p0))
        if self.llr >= self.upper:
            self.verdict = "accept"  # candidate is meaningfully better
        elif self.llr <= self.lower:
            self.verdict = "reject"  # no material difference from baseline
        elif self.n >= self.max_games:
            self.verdict = "inconclusive"  # hit the safety cap without a confident decision
        return self.verdict

    @property
    def decided(self):
        return self.verdict is not None

    @property
    def win_rate(self):
        return self.wins / self.n if self.n else 0.0

    def status(self):
        return (f"n={self.n} wins={self.wins} ({self.win_rate:.1%}) "
                f"LLR={self.llr:+.3f} (bounds {self.lower:.3f}..{self.upper:.3f})"
                + (f" -> {self.verdict}" if self.verdict else ""))


def elo_to_p(elo_diff, base_p=0.5):
    """Convert an Elo difference to a win probability, anchored at base_p (usually 0.5)."""
    base_elo = -400 * math.log10(1 / base_p - 1) if base_p != 0.5 else 0
    return 1 / (1 + 10 ** (-(base_elo + elo_diff) / 400))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Standalone LLR-bound calculator / quick sanity check.")
    ap.add_argument("--p0", type=float, default=0.5, help="null-hypothesis win rate")
    ap.add_argument("--p1", type=float, default=0.55, help="alternative-hypothesis win rate")
    ap.add_argument("--elo1", type=float, default=None, help="alternative as an Elo gain over p0 instead of --p1")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    args = ap.parse_args()
    p1 = elo_to_p(args.elo1, args.p0) if args.elo1 is not None else args.p1
    lower, upper = llr_bounds(args.alpha, args.beta)
    print(f"p0={args.p0} p1={p1:.4f} alpha={args.alpha} beta={args.beta}")
    print(f"LLR bounds: reject <= {lower:.3f}, accept >= {upper:.3f}")
    print("Rule of thumb worst-case game count (both hypotheses equally likely): "
          f"~{int((upper - lower) / abs(math.log(p1 / args.p0))) if p1 != args.p0 else '?'} games")
