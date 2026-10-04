# wNN sweep (panel_zig, --set live, seeds 1,2, vs baselines/y7_12_49, n=40)

Per-map order: trauma autarky trophy default dilemma devil slithery schooltime portals qos (wins/4)

| wNN | wins/40 | win% | per-map | vs wNN=2 | CPU max |
|---|---|---|---|---|---|
| 0 | 11 | 27.5 | 1 1 0 2 1 0 1 3 2 0 | -12 | not in logs |
| 1 | 20 | 50.0 | 1 2 2 3 3 2 1 3 2 1 | -3 | not in logs |
| 2 (vB19) | 23 | 57.5 | 1 0 3 3 4 3 1 3 2 3 | 0 | not in logs |
| 4 | 17 | 42.5 | 0 1 3 0 2 3 1 3 2 2 | -6 | not in logs |
| 8 | 20 | 50.0 | 2 1 3 0 2 3 1 3 2 3 | -3 | not in logs |

Read: SE ~8pp (~3 wins). Only wNN=0 is clearly worse (-12, ~1.5 SE-of-difference); 1/2/4/8 are statistically indistinguishable (non-monotonic, so mostly noise). wNN=2 is nominal best but not proven. No FAILED/timeouts in any log.
