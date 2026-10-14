"""Build a bot dir to wasm with the judge's clang; rebuild when ANY source in the dir changed (headers too).

    python tools/buildwasm.py BOT_DIR     # prints the path of the cached .wasm

unswbc's own cache keys on .cpp files only (a header-only edit silently reuses a stale build); this keys on every
.cpp/.hpp/.h/.cc file. Builds land in wasm_cache/ at the repo root.
"""
import hashlib, pathlib, sys, shutil, json
from unswbc import clangtool
from unswbc.sandbox import _cache_dir
d = pathlib.Path(sys.argv[1]).resolve()
tool = clangtool.toolchain()
inputs={p.relative_to(d).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob('*')) if p.is_file() and p.suffix in ('.c','.cpp','.cxx','.cc','.hpp','.h','.toml')}
compiler={p.relative_to(tool).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(tool.rglob('*')) if p.is_file()}
h = hashlib.sha256(json.dumps([inputs,compiler,hashlib.sha256(pathlib.Path(clangtool.__file__).read_bytes()).hexdigest()],sort_keys=True).encode()).hexdigest()[:16]
out = pathlib.Path(__file__).resolve().parents[1] / "wasm_cache" / f"{d.name}-{h}.wasm"
if not out.exists():
    for old in (_cache_dir() / "wasmbots").glob(f"{d.name}-*.wasm"):
        old.unlink()
    built = clangtool.build(d)
    out.parent.mkdir(exist_ok=True)
    shutil.copy(built, out)
print(out)
