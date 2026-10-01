import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
MAPS = ROOT / "maps"

# Replays of OTHER teams' games stay out of git (the repo's .gitignore keeps ladder/ out for that reason), so the
# fixtures are copied from the local ladder/ folder on first use; tests needing them skip when it is absent.
import shutil
import pytest

FIXTURES = {
    "690143.replay": "ladder/scout_fresh/91/690143.replay",
    "690643.replay": "ladder/scout_fresh/91/690643.replay",
    "690174.replay": "ladder/scout_fresh/70/690174.replay",
    "698131.replay": "ladder/scout_self/98/698131.replay",
}
REPLAY_DIR = ROOT / "tests" / "data" / "replays"


def ensure_fixtures():
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    for name, src in FIXTURES.items():
        dst = REPLAY_DIR / name
        if not dst.exists() and (ROOT / src).exists():
            shutil.copy(ROOT / src, dst)
    missing = [n for n in FIXTURES if not (REPLAY_DIR / n).exists()]
    if missing:
        pytest.skip(f"replay fixtures missing ({', '.join(missing)}); needs the local ladder/ folder", allow_module_level=True)


@pytest.fixture(autouse=True, scope="session")
def _fixtures():
    try:
        ensure_fixtures()
    except pytest.skip.Exception:
        pass
