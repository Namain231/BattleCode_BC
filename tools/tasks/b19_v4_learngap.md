# Task b19_v4_learngap — port online bed-gap learning (`learnGap`) from s2_gP into a copy of vB19

Repo: C:\Users\sohan\Downloads\BattleCode_BC (Battlecode "Loong" C++ bot). No memory of earlier work assumed.

Working dir: `viper_b19_v4/` (already a copy of `baselines/vB19/`). Edit ONLY `viper_b19_v4/main.cpp`. Never touch `baselines/`.
Source of the feature: `baselines/s2_gP/main.cpp` (search `learnGap`, `ptLast`, `ptRoundP1`, `ptMax`, `ptMinFresh`, `ptCycles`).

## Why
On UNSEEN maps (`KM == nullptr`) the bot has no stored pearl-bed gap tables (`gmin/gmax`), so farm valuation and the
network's bed-rate plane are blind. s2_gP learns each bed's gap range online; vB19 lacks it. The final tournament
uses unseen maps.

## Changes
1. Copy the block "ONLINE BED-GAP LEARNING" (the comment, the `static int ptLast[MAXN]...` declarations and the
   `learnGap(int c, int pt)` function) from s2_gP into vB19's main.cpp at the equivalent place (after `gmin/gmax`
   are declared, before first use; both files are ~identical in that region).
2. In vB19's pearl-update loop (around the line `if (V.ptime[i] < 0 && gmax[c] < 0) { gmax[c] = 0; gmin[c] = 0; }`,
   followed by the `if (KM) { // MAPFIX ...}` block), add `if (!KM && V.ptime[i] >= 0) learnGap(c, V.ptime[i]);`
   exactly as s2_gP does (s2_gP ~L424). Leave the KM / MAPFIX branch unchanged.
3. Check the three places in s2_gP guarded by `!KM` that relate to this feature (e.g. ~L624
   `else if (!havePrev && !KM && ROUND == 0 ...)`, and any use of `gmin/gmax` for unseen maps in the network input
   or farm bonus). Port only those that depend on learnGap; report any you skipped and why.
4. Reset the new arrays where vB19 resets per-game map state (look for where `gmax`/`gmin` are reset when a map is
   (re)identified, as s2_gP does). Mark every edit `// V4`. Change nothing else, no reformatting.

## Verify (real output only)
- `uv run --python 3.11 --with unswbc python tools/buildwasm.py viper_b19_v4` succeeds.
- Smoke on an UNSEEN map: `uv run --python 3.11 --with unswbc python tools/panel_zig.py viper_b19_v4 baselines/vB19 out/b19v4_smoke --maps maps_rm_dev/<first .map file in maps_rm_dev without extension> --seeds 1 -j 2`
  must produce replays; report our CPU max (keep under ~65M).

## Report
Append to `AGENT_LOG.md` with >>: `- [2026-10-02] [executor] [b19_v4_learngap] <what ported, build, smoke, CPU, skipped items>`.
Final message: `diff --strip-trailing-cr baselines/vB19/main.cpp viper_b19_v4/main.cpp`.
