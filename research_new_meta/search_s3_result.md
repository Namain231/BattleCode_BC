# search_s3_proto result (2026-10-02)

Status: resumed by search_followup; M0 completed against official toolkit1.2.7. Initial M1 finished4/20; M2 pilot running; M3 unmeasured so far.

## Followup method and evidence (2026-10-02)

New judge: /home/sohan/toolchains/zig-judge-out-serve/bin/loong-judge.
Use current official1.2.7 copied temporarily into out/search_followup_s3/engine-1.2.7.wasm; the setup report's ~/venv engine is old1.2.2 and is unsuitable.
Python runner: /home/sohan/venv/bin/uv run --python3.11 --with unswbc --with numpy (isolated uv installation, no system packages).
Policy: tools/search_proto/serve_search.py. Panel: tools/search_proto/panel.py. Targeted lifecycle check: tools/search_proto/check.py.
Rollouts use tools/engine_sim.py because it is already callable from Python; no binding or C++ engine edit was needed.
Opponent is unchanged cached wasm_cache/vB19-4c23c57aea0e3e6f.wasm. No replay/pickle is written; compact JSON retains judge text and exit status.

M0: trivial served team B on Default completes152rounds, loses to vB19 teamA; wall17.435s, served mean0.267ms/turn.
The source-inspected framing below was exercised in a full game. Policy replies include PROTOCOL3 and ENDTURN. No-action reply models suicide.
Lifecycle checks pass: exported network reference logits, countdown aging/expiry, ID highwater, no persisted guessed child IDs, suicide wire parity, terminal r499 depth stop, unknown enemy queen exclusion.

World estimate excludes map-file initial dragons and seeded hidden countdowns. It merges received per-turn body/pearl observations, remembers own predicted body, truncates unobserved bodies, and expires enemy-head sightings after one round. Known live-map topology/rates are allowed, as in the shipped map recognizer. Tail-only observations block immediate moves but have no imagined moving head. Future pearl spawns use observed positive countdowns only; expired/unobserved beds do not predict spawns.
Search samples two stochastic opponent trajectories per evaluated candidate. Net probabilities above5% of legal probability mass are retained, with net best always present and at most4arms. UCB1 initializes all arms plus one allocation. Its allocation value uses0.5+0.5*tanh((leaf-rootmaterial)/8); final candidate ranking uses raw mean leaf score, avoiding saturation ties. Rollouts execute the current partial round from requesting ID, then ascending IDs/newborns each round, stopping at r499. Score is signed total material, with penalties/rewards for queens known alive at rollout start and killed inside rollout. Unknown queens earn no death reward. Queen length receives dominant weighting at r499.

Performance pilot: the initial untriggered whole-world policy did not finish either Trauma game after639.8s;5072/5359turns,117/123ms mean decision time,79/81 unique network calls per turn. These incomplete runs are excluded from outcome statistics and retained under original_pilot/. The fresh variant follows search_layer_plan.md§d.1: search if an observed/remembered enemy head's3*ceil(L/4)+1 reach intersects ours through known topology, or normalized top-two legal prior gap≤0.1; always search the fixed queen when at least two candidates remain. A single retained candidate skips search. Every modeled dragon still acts sequentially in each searched rollout. No branch is stopped early by a timing budget. A per-decision seed123+round*4096+id prevents earlier skipped searches from changing later reply samples; the initial pilot used a game-global RNG and is a separate variant.

Limits: this tests a net-only policy with simple legal/split checks against net-guided search in the same served harness, not search added to the full vB19 rule layer. Shared observations make it an upper bound on communication, while partial body estimates and a net-only opponent model add error. Tail-only root blockers are omitted in rollout. Truncated bodies shorten simulated effective lengths/queen value. Enemy state is retained at most one round without motion belief. Head trades are excluded when an empty legal step exists; split size is fixed2. The first rollout round is partial, so depth3 means the requesting-ID suffix plus two full rounds. Rollouts cannot infer real hidden-team elimination and continue modeled rounds until the requested horizon/r499. Depth histogram is the maximum depth reached per decision, not a histogram of individual rollout lengths. Zero metered served points do not establish wasm CPU feasibility.

Initial M1: 4/20 wins (Trophy both sides, SchooltimeA, QoSB). Its queen DEATH timestamps are last-served-observation estimates and cover own queen only; this historical panel is preserved as net_initial_summary.json. Instrumentation-only rerun is scheduled with temporary replays, extracting both queens' exact zero-based death rounds and deleting each replay immediately (no pickle). Survivor queens are absent from death dictionaries.

The historical blocked attempt below is retained as provenance, not the current status.

## Method and prerequisite checks

Read the supplied search plan, S0 audit, simulator status, served-policy source and protocol documentation. The intended experiment is a served numpy policy against unchanged baselines/vB19, using the same harness for net-only and search, the ten live maps, both seats and seed 1 (20 games per arm), at no more than two concurrent games. Follow with depth and queen-term ablations. This is a research prototype, not a submission.

The installed /home/sohan/toolchains/zig-judge-out/bin/loong-judge rejects `--serve /tmp/search_s3_probe.sock --serve-team B` with `UnknownFlag`. Its printed usage has no served-policy flags. `which just nim` returns exit 1 and no paths in WSL Ubuntu. /home/sohan/toolchains/zig-linux/zig reports 0.16.0. Thus the requested `just zig-judge-build` fallback is unavailable. Per the task's explicit instruction, no system packages were installed and work stopped at this prerequisite blocker.

Additional resource finding: `df -h /mnt/c` reports only 102-104 MB available, rather than the expected approximately 6 GB. WSL's root filesystem reports 953 GB available. No unrelated data was deleted.

## Served protocol (source inspection, not a full-game validation)

Source: /home/sohan/the-loong-game/harness/zig_judge/src/served.zig.
The judge connects to the external process's UNIX socket. Headers are newline terminated:
- GAME <seed> <A or B>: selected team and seed.
- SPAWN <id> <bytes>: exactly that many bytes of the dragon's init block follow.
- TURN <id> <bytes>: exactly that many bytes of its observation follow; the policy replies with a decimal byte count plus newline and the reply text.
- DEATH <id>: notification for a served dragon.
- END <A, B or -> <rounds>: winner and rounds played.

The ordinary turn payload includes ROUND and one dragon's local observation. Turns are answered individually, not as a simultaneous round batch. One external process handles all served dragons and can merge their observations and retain team-wide knowledge. This makes the proposed experiment an upper bound relative to the shipped per-dragon bot; it must not receive hidden opponent state or treat accumulated observations as simultaneous truth.

## Results

| Milestone | Games | Win rate | Queen deaths / timings / depth |
|---|---:|---|---|
| M0 trivial served policy | 0 | Unmeasured | Blocked by old judge and unavailable rebuild tools |
| M1 net-only | 0 | Unmeasured | Unmeasured |
| M2 depth-3 search | 0 | Unmeasured | Unmeasured |
| M3 ablations | 0 | Unmeasured | Unmeasured |

No policy implementation, wasm build, replay or pickle cache was created. Baselines, shipped bots and engine_cpp were not edited.

## Verdict and resumption

INCONCLUSIVE: neither GO nor NO-GO for a wasm search implementation is supported by this run. The offline S0 thresholds do not substitute for the requested direct experiment. A current judge supporting --serve, or available just/Nim prerequisites for the requested rebuild, is needed to resume M0. Restore disk headroom before building or writing experiment outputs to C:. Once the harness works, implement and validate the served policy, then run the paired baseline/search panel and ablations before deciding whether a cheaper rollout net and a 100M-point wasm implementation are justified.
