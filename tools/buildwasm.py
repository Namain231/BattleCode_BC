"""Build a bot dir to wasm with the judge's clang; rebuild when ANY source in the dir changed (headers too).

    python tools/buildwasm.py BOT_DIR     # prints the path of the cached .wasm

unswbc's own cache keys on .cpp files only (a header-only edit silently reuses a stale build); this keys on every
.cpp/.hpp/.h/.cc file. Builds land in wasm_cache/ at the repo root.
"""
import hashlib, pathlib, sys, shutil
from unswbc import clangtool
from unswbc.sandbox import _cache_dir
d = pathlib.Path(sys.argv[1]).resolve()
h = hashlib.sha256(b"".join(p.read_bytes() for p in sorted(d.iterdir()) if p.suffix in (".cpp", ".hpp", ".h", ".cc"))).hexdigest()[:16]
out = pathlib.Path(__file__).resolve().parents[1] / "wasm_cache" / f"{d.name}-{h}.wasm"
if not out.exists():
    for old in (_cache_dir() / "wasmbots").glob(f"{d.name}-*.wasm"):
        old.unlink()
    built = clangtool.build(d)
    out.parent.mkdir(exist_ok=True)
    shutil.copy(built, out)
print(out)
