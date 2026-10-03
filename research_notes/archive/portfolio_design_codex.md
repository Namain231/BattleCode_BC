# Portfolio bot design for Battlecode 2026

## Recommendation

Treat this as **one coordinated team policy with a selectable movement core**, not as several complete bots competing inside each process. Keep the current best rule core as the safe default. Select another core only when there is reproducible evidence that it wins in a regime the default loses. Share one protocol, one map belief, one queen/endgame plan, and one sonar codec across all cores.

The important unit of selection is the whole team/game. Selecting a core independently by dragon or by local view creates a mixed team whose members can disagree about splitting, feeding, target assignment, and the queen. That coordination cost can erase a specialist's advantage.

## 1. Combining the C++ cores safely

### Preferred architecture

Create a small common shell and adapt each core behind a narrow interface:

```cpp
struct Observation; // parsed once from the engine input
struct Action;      // one validated output action
struct TeamState;   // decoded shared plan and observations

namespace core_y10 { void choose(const Observation&, const TeamState&, Action&); }
namespace core_s475 { void choose(const Observation&, const TeamState&, Action&); }
```

The shell owns `main`, stdin/stdout, parsing, protocol validation, map/regime selection, shared sonar encoding, and final action serialization. A core receives a read-only normalized observation and returns an action; it never reads stdin, prints protocol output, or makes its own final choice of team regime. Keep each imported core's helpers and mutable state private to that core. Convert mutable file-scope globals into an explicit `CoreState` passed to `choose` if any state must survive turns. Since a split child starts without its parent's memory, correctness must never depend on that state being inherited.

If the build requires a single translation unit, first turn each imported body into an include fragment that contains **no** headers, `main`, input/output, global protocol state, or generic macros. Include standard/library headers before any namespace wrapper. Put the cleaned body in a uniquely named namespace and prefix macros and generic helpers. Do not simply write `namespace x { #include "main.cpp" }`: standard headers may then declare their contents in the wrong namespace, and each bot likely defines `main` and colliding globals. If the build allows multiple objects, separate translation units are safer; expose only the adapter interface above.

### What not to combine

- Avoid choosing only parameter sets unless the candidate cores really share the same control flow. vB.17 and Y.10 have meaningful rule differences; pretending they are parameter variants hides coupling and makes a supposed specialist hard to validate.
- Avoid carrying multiple whole-core protocol implementations. `cand_y10/main.cpp`, `opponents/s475/`, `opponents/vb17/`, and `opponents/vb18/` should contribute decision logic through adapters, not competing parsers, `main`s, sonar encoders, or output routines.
- Avoid broad textual renaming as the final design. It misses macros, overloads, inline functions, templates, and static state. Use source/translation-unit isolation and explicit interfaces; compile each adapter early to expose ODR and symbol conflicts.
- Do not let any specialist emit sonar independently. Existing queen gossip is part of the team protocol; message ownership belongs to the shell.

### Core lifetime and selection point

Choose a team mode from the init block when a known map can be identified immediately; otherwise maintain an `UNDECIDED` state and classify from the first few turns of observations. Make the choice sticky for the game (e.g. finalize by round 12–20), encode it in sonar, and never let individual dragons re-select after seeing a locally unusual patch. Every split child repeats the same deterministic known-map/feature procedure and then accepts a valid teammate decision. A child that has not yet heard one uses the safe default core and the shared plan protocol. The first implementation should choose **one core for all dragons**. Per-role portfolios (queen vs worker, scout vs feeder) are a later experiment, not an initial feature.

## 2. Regime agreement with partial observation and sonar

Use a three-class belief (`OPEN`, `MAZE`, `PORTAL`) plus `UNKNOWN`; portal is an overlay because a portal-heavy map can also be open or maze-like. Keep a confidence/valid bit. Do not force the team into a low-confidence label.

### Decision order

1. **Known map:** reuse the map-candidate matching in `cand_y10/main.cpp` (`KNOWN_MAPS`, `activateMap`, and the candidate filtering/matching path). Also inspect `opponents/s475/knownmap.hpp`'s round-0 `filterBySpawn` approach. A unique high-confidence match gives every dragon the same label from spawn/map geometry. Keep map identity separate from regime: a recognized map can map to a measured specialist, but an unknown map still receives generic features.
2. **Map size prior:** use width and height only as a weak prior / candidate filter. Many layouts can share dimensions. Do not use dimensions as the final classifier.
3. **Local evidence:** aggregate early visible terrain and local connectivity statistics. Use cumulative counts and sample counts, not a single 7x7 patch. Weight repeated observations of the same cell once when possible; if absolute coordinates are unavailable in the input, use per-turn statistics and accept that sampling bias is noisier.
4. **Sonar consensus:** transmit the best known map/regime decision and confidence. On conflicting valid reports, use a deterministic rule: highest confidence; then known-map match over feature inference; then lowest reporting dragon ID. Freeze the result by a fixed round. This keeps all processes convergent rather than oscillating.
5. **Fallback:** until confidence is adequate or a teammate report arrives, run the champion/default policy with the common team protocol. For a newly split child with no parent memory, read the init block, run the same classifier, and listen for gossip. If it is still undecided, use the default policy and emit the current belief; never invent a child-specific mode.

### Sonar message layout

Reserve a versioned, tagged payload in the existing sonar message path (trace the producer/decoder in `cand_y10/main.cpp` before allocating bits, because its queen gossip is already live). A suggested compact payload within each available 64-bit value is:

| Bits | Field |
|---|---|
| 0–3 | magic/version (reject old or unrelated words) |
| 4–6 | message kind: regime, map ID, queen/plan, or reserved |
| 7–9 | regime: unknown/open/maze/portal-overlay/mixed |
| 10–13 | confidence bucket |
| 14–21 | known-map ID or 255 for unknown |
| 22–29 | decision round and/or source ID fragment |
| 30–37 | team-plan version and plan flags |
| 38–53 | optional quantized feature summary |
| 54–63 | checksum / remaining reserved bits |

Exact packing depends on the engine's ray/message semantics and the current queen format; this is a schema proposal, not a claim that all 64 bits are available in every ray. Prefer reusing one existing team-wide message field if the current format already has spare bits. Preserve the old queen location/length/round fields and add a message-kind/version discriminator, or migrate all readers/writers atomically. Do not reinterpret old payloads silently. Validate magic, version, bounds, freshness, and checksum before accepting a report. If messages are repeated on multiple rays, deduplicate by `(kind, source, round)`.

To keep the whole team coherent, regime gossip must carry the **team plan version** too. Mode changes are legal only before the finalize round; after that a later contradictory message is diagnostic and ignored. A valid known-map identity outranks local regime estimates, but all processes should still use the same map-to-core table embedded in the binary.

## 3. Useful features from partial 7x7 views

The classifier should estimate behaviors the policy cares about, not attempt perfect global cartography. Compute on the passable/blocked terrain exactly as defined by `docs/kelp-and-portals.md`; keep unknown cells distinct from known blocked cells. Vision does not cross portals, so portal destinations and cells beyond them are missing samples, not evidence of walls.

### High-value features

- **Portal incidence:** count visible portal endpoints and distinct paired links if the view exposes pairing; otherwise count endpoints only. Normalize by observed traversable cells and track whether portals have appeared on multiple turns. Portal count/density and usable portal links are the clearest portal-specialist signal.
- **Local passable degree:** for each observed traversable cell, count known traversable cardinal neighbors. Track the fraction with degree 1 (dead ends), degree 2 (corridor), degree 3–4 (junction/open). Exclude cells adjacent to unknown terrain from a hard dead-end count; store a lower-bound/uncertain count instead.
- **Corridor score:** proportion of sampled passable cells with degree 2, plus the length of observed degree-2 chains. Long narrow chains mean routing, congestion, and dead-end avoidance matter.
- **Junction / branching score:** degree-3/4 fraction and number of distinct branches reachable from the current local patch. Open maps tend to have many alternate paths; mazes have constrained routes.
- **Kelp density and obstruction pattern:** visible kelp / total observed cells, plus connected runs or barriers. Density alone is weaker than its effect on passable degree and route connectivity.
- **Local openness:** traversable fraction and number of distinct two-step destinations from the current cell. This approximates maneuvering freedom without knowing the full board.
- **View stability over time:** newly seen cells per round and fraction of terrain revisits. A wider sampling footprint improves confidence; repeated overlap helps avoid double-counting.
- **Dimensions and aspect ratio:** cheap weak prior only. The board wraps, so distance/connectivity features must use toroidal adjacency where coordinates are known.

An initial scalar score is enough: `maze_score = corridor_fraction + dead_end_fraction - junction_fraction`; `portal_score = portal_endpoints / max(1, observed_passable)`; `open_score = junction_fraction + traversable_fraction - dead_end_fraction`. Use thresholds trained on the available map corpus, calibrated against known map labels. Keep three scores and confidence rather than forcing a single hard class. Tune thresholds from map samples/replay observations, not intuition. A local 7x7 estimate cannot safely infer global dead-end counts, global corridor width, or fountain ownership; label them as estimates.

### What is most predictive?

For core selection, likely rank: (1) verified map identity, (2) visible portal density/link usability, (3) degree/corridor/junction distribution, (4) accessible route choice count, then (5) kelp density and board dimensions. Portal geometry changes movement and vision directly. Maze topology changes access and congestion. Raw kelp density and size can correlate with regime but are easy to misread from one spawn-centered view. Record per-map feature vectors and later check whether the chosen specialist actually wins by those vectors; if not, the classifier is solving the wrong problem.

## 4. Minimal version worth testing in a few hours

### Scope

1. Start with `cand_y10/main.cpp` as the sole core and protocol owner. Add a `PortfolioState` with known-map ID, feature accumulators, confidence, and selected core. Do not import five complete bots at once.
2. First add regime detection and sonar gossip, but keep the selected action core fixed to Y.10. This tests whether map identification and consensus work without policy confounds.
3. Add **one** genuinely different specialist only if existing results show a reproducible map-specific advantage. Initially, map known-map IDs to Y.10 or that one core; for unknown maps, remain Y.10. Do not claim a portfolio win from putting in a weaker bot as a specialist.
4. Share splitting/economy, queen assignment, feeding/endgame, and sonar messages in the common shell where feasible. If importing a specialist makes those protocols inseparable from its movement logic, select the whole core but keep exactly one standardized message adapter and verify its action output against the engine protocol.
5. Add a compile-time `PORTFOLIO_FORCE_CORE` / `PORTFOLIO_TRACE` switch for controlled ablations. Any diagnostic text must go to stderr only if the protocol permits it; otherwise encode compact mode/feature diagnostics in replay-visible sonar without disturbing the decision messages.

### Evaluation on the real ladder

Offline self-play is not a promotion signal here. Use unranked real-ladder scrims with ranked disabled, fixed opponent set, and explicit map IDs (the project notes list the live map IDs in `AGENTS.md`). Keep the active champion and core controls unchanged between conditions. Run paired batches with the same teams and map set, swap our side where the API/test harness permits, and alternate control/portfolio order to reduce time drift. Include every map type, not only the expected specialist maps.

Compare at least:

- Y.10 forced on every game;
- specialist forced on every game;
- portfolio selector enabled;
- optionally the safe fallback on every game as a diagnostic.

Log game ID, map, side, opponent/submission, recognized map, feature vector, confidence, selected mode, core, winner, ending reason, and final longest/total length. Use enough repeated games to separate a small edge from noise; inspect intervals by map/regime and do not promote on aggregate wins driven by one map. Follow the repo's loss-analysis rule: analyze **every loss**, grouping causes such as opening access, portal routing, friendly head-ons, feeding, CPU/crash, and longest-dragon tiebreak. A portfolio is worth keeping only if it improves over the strongest forced core on the maps it selects for, does not materially regress elsewhere, and improves overall in fresh batches. If it only matches Y.10, keep the simpler Y.10.

The existing `tools/ab_live.py`/ladder replay-header checks and `tools/build_record.py` can help attribute builds and verify which code ran. For these tests, do not activate/challenge ranked opponents; use the unranked ladder path and ensure each game actually used the intended submission/build. Because the user's own handoff says only one session should run ladder jobs and active builds can change mid-series, serialize submissions and record replay-header build IDs.

## 5. When a portfolio will not help

- **No real conditional advantage:** if the candidate cores are near ties or one dominates, selection adds cost without value. The handoff's panel was saturated and sometimes disagreed with ladder results; it also reports Y.10 and Y.8m tied. Establish real per-map/per-style advantages first.
- **Weak or late features:** a 7x7 view samples a biased area, new children restart, and vision stops at portals. A classifier may label the spawn neighborhood rather than the strategic map. Map identity or a stable shared decision is essential.
- **Coordination mismatch:** different split thresholds, target selection, feeding protocols, or queen plans can make specialists interfere. This is the largest structural risk. Keep one team-level protocol and change movement/economy only when measured.
- **Regime is not the causal variable:** map topology may not explain the losses. Opponent style, spawn side, fountain placement, early random pearl countdowns, and current unit/length state may matter more. If the champion's losses are caused by late feeding or head-ons on both open and maze maps, an open/maze portfolio misses the cause.
- **Small sample / overfitting:** 10 known maps are not enough to fit a rich classifier, and a few wins on a map can be noise. Use a tiny rule classifier, leave maps/opponents out when tuning, then confirm on fresh games.
- **Binary and operational cost:** duplicated large cores threaten the 4 MB zip, 48 MB memory, and maintainability. More code also means more protocol and CPU paths to validate. Keep only a single specialist initially.

If these conditions apply, prefer a targeted shared improvement: fix one measured loss mechanism in the champion (e.g. a proven portal safety, feeding, or endgame issue), or add a small per-action heuristic guarded by observable state. The handoff's measured lessons are useful: some maze-only fixes helped the Y.8 line, while broader feeding/endgame changes often failed on open maps and panel rankings did not always predict ladder outcomes. A behavior-level gate such as "avoid a portal exit occupied by the gossiped queen" may transfer better than switching the entire bot based on an uncertain map label.

## Implementation checklist

- [ ] Read and match the exact input/output and terrain symbols in `docs/protocol.md`, `docs/map-info.md`, `docs/vision.md`, `docs/kelp-and-portals.md`, `docs/splitting.md`, and `docs/sonar.md` before coding.
- [ ] Trace `cand_y10/main.cpp`'s `KNOWN_MAPS`, `activateMap`, candidate matching, and queen gossip; trace `opponents/s475/knownmap.hpp::filterBySpawn`.
- [ ] Define a versioned sonar schema and preserve queen messages.
- [ ] Make classifier output deterministic, sticky, and identical across processes.
- [ ] Integrate one specialist via adapter only after a measured reason exists.
- [ ] Verify protocol validity, CPU/memory/zip budget, split-child fallback, and team consensus.
- [ ] Evaluate by unranked real-ladder paired batches; analyze every loss; retain only demonstrated gains.
