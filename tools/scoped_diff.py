"""Scoped diff for tools/delegate.sh: show ONLY what an agent changed, not the whole dirty working tree.

    scoped_diff.py snap SNAPDIR      # before the executor runs: remember every dirty/untracked file
    scoped_diff.py diff SNAPDIR      # after: unified diff of files that changed since the snapshot

secrets.env, out/, ladder/, wasm_cache/, __pycache__ and files over 2 MB are never read or copied.
"""
import hashlib, os, subprocess, sys, difflib, shutil

SKIP_PREFIX = ("out/", "ladder/", "wasm_cache/", "replays/", "archive/", ".git/")
SKIP_NAMES = {"secrets.env"}
MAX = 2 * 1024 * 1024


def files():
    out = subprocess.run(["git", "ls-files", "-m", "-o", "--exclude-standard", "-z"], capture_output=True).stdout
    for p in out.decode("utf-8", "replace").split("\0"):
        p = p.replace("\\", "/")
        if not p or p in SKIP_NAMES or p.startswith(SKIP_PREFIX) or "__pycache__" in p or ".snap/" in p or os.path.basename(p) in SKIP_NAMES:
            continue
        if os.path.isfile(p) and os.path.getsize(p) <= MAX and not p.endswith(".diff") and not any(t in p for t in (".exec.", ".critique.", ".verify.", ".backend.")):
            yield p


def digest(p):
    return hashlib.sha1(open(p, "rb").read()).hexdigest()


def snap(d):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.txt"), "w", encoding="utf-8") as f:
        for p in files():
            f.write(f"{digest(p)}\t{p}\n")
            dst = os.path.join(d, "files", p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(p, dst)


def read_lines(path):
    try:
        return open(path, encoding="utf-8", errors="replace").read().splitlines(keepends=True)
    except OSError:
        return []


def diff(d):
    before = {}
    for line in open(os.path.join(d, "index.txt"), encoding="utf-8"):
        h, p = line.rstrip("\n").split("\t", 1)
        before[p] = h
    after = {p: digest(p) for p in files()}
    n = 0
    for p in sorted(set(before) | set(after)):
        if before.get(p) == after.get(p):
            continue
        a = read_lines(os.path.join(d, "files", p)) if p in before else []
        b = read_lines(p) if p in after else []
        sys.stdout.write("".join(difflib.unified_diff(a, b, f"a/{p}", f"b/{p}")))
        n += 1
    print(f"\n[scoped_diff: {n} file(s) changed by the executor]")


if __name__ == "__main__":
    {"snap": snap, "diff": diff}[sys.argv[1]](sys.argv[2])
