Candidate only; no promotion or ladder claims.

All eight feature defaults remain independently switchable in Params.
qposFrom=0 disables the new early schedule and preserves qf's legacy r200 QPOS.
With every feature off, the legacy scheduler, radar, gossip, portal probes,
packet interpretation and scoring remain qf-compatible. laneRays controls
only the new queen schedule: 3 omits the back cast AND its inference; 4
includes refracted back observations in the posterior.

Encrypted packets use an authenticated MAC domain distinct from legacy
plaintext. Decode rejects domain/round ambiguity instead of guessing from
plausibility. Legacy plaintext is accepted only by a valid legacy MAC.
STATUS accepts authenticated protocol IDs including unseen teammates.
Active feature builds sign radar sentinels; enemy zero words remain evidence.
All-off builds retain the original unsigned zero sentinel for exact parity.

STATUS describes its sender and an unlocalized alarm; it never fabricates
an enemy location. Interception uses deduplicated CURRENT visible enemy
heads only. Current visible friends override stale reports, queens cannot
occupy interceptor slots, and reports are capped at 64. Ranks are computed
once per threat (at most eight), with shared-budget guards. At most one
local interceptor is selected per observed enemy; the total scoring bonus
is clamped to [-8,8] and does not reward options with high death risk.
Incomplete distributed views cannot guarantee four survivors.

Guard-zone scoring penalizes new body obstruction at queen exits via the
real wall/portal neighbor table. Existing body obstruction does not stack
the same penalty across every option. Feeder exemption requires reaching
the queen approach, rather than merely having feeding mode enabled.
The queen has no unconditional friend-report penalty.

Relay dedupe is keyed by kind/source/source-round and committed only after
the selected packet is emitted. Unselected eligible packets remain pending.
Two-ray STATUS/radar turns skip ambiguous single-ray enemy attribution.
Queen refraction uses the emitted parent body, including split/amputation.
Body membership is precomputed; ray walks respect the shared CPU reserve.

Focused checks: g++ -std=c++17 -O0 -x c++ viper_y96qg/packet_check.txt
-o viper_y96qg/packet_check.exe, then execute it (do not submit the executable).
Native packet, legacy, high-ID, zero-word, and relay-selection checks passed.
All-off parity: seed 3, maze and trauma, both sides (4 games); complete
summaries and decoded gameplay/sonar/indicator events match qf, excluding
CPU measurements. Outputs: out/qg_off_chk and out/qf_chk.

Cheapest ablation order: parity first; guardIntercept off; guardZone off;
enemyPing off; laneEcho off while preserving casts (then QPOS timing and
STATUS off); encryption separately. Keep freeze off. No larger panel run.

Unverified: ladder effect, ablation performance, multi-hop delivery rates,
global interceptor coordination, posterior calibration with moving blockers,
cryptographic confidentiality, and freeze efficacy.

Final verification (2026-10-04): final-source all-off parity passed all
4 requested games, including complete summaries and decoded sonar,
actions, indicators, splits and deaths. The all-off main.cpp matches the
candidate exactly except for the eight requested feature defaults.
Final CPU smoke: australia and around_unsw, seed 3, both sides (4 games).
Candidate maximum: 64,464,075 points, below 66M. CPU is measured from
judge stdout because local replay instrumentation is stripped.
Packet/legacy/high-ID/zero-word/relay checks passed on the final source.
Final judge-clang build passed. Evidence: verification.json, cpu_smoke.txt,
out/qg_off_chk/summary.json and out/qf_chk/summary.json.
