Yardstick vs real champion baselines/y7_12_nn1 (Zig judge, live set, 1 seed x 2 sides = 20 games, 2026-10-02). n=20 => ~11pp standard error: 10/20 vs 9/20 is not distinguishable.

| candidate | wins/20 | win% | per-map wins (of 2) | queen death rounds (our queen, per game) | gate | max CPU |
|---|---|---|---|---|---|---|
| baselines/vB19 | 10 | 50% | trauma1 autarky1 trophy1 default2 dilemma1 devil0 slithery0 school1 portals2 QoS1 | 368,339,5,5,282,5,5,491,165,5,5,179,323,299 | PASS (threshold 50%, 0 queen regressions) | ~77M (schooltime, near limit) |
| viper_b19_v4 | 9 | 45% | trauma0 autarky1 trophy1 default2 dilemma1 devil0 slithery0 school1 portals2 QoS1 | same as vB19 except trauma A 491 | FAIL (45% < 50%; 0 queen regressions) | ~77M |

Notes: queen death "5" appears on autarky/dilemma/slithery in both sides and both candidates (analyze.py q_death; likely trapped/swapped queen artifact, unverified). v4 differs from vB19 only on trauma (1 game). Both lose devil and slithery 0/2. No run failures. Logs: out/yard_vB19.log, out/yard_v4.log.
