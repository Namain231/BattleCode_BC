# Sonar and echo: underused tactics under the 2026-10-01 rules

Researcher note, 2026-10-02. No code was edited. Tags: **[D]** = docs (file:line), **[M]** = measured here on
`ladder/scout_v6` (306 top-team games + 18 of ours, new rules, scripts listed at the end), **[L]** = our own earlier
ladder/local evidence (old rules unless stated), **[R]** = reasoning, **[U]** = unverified.

Top teams still run old-rule bots in many respects. Their sonar habits are used below as evidence of what is
possible and cheap, not as a picture of what is optimal.

---

## 1. Exact mechanics

### SONAR (sending)
- **Up to 4 words per turn, one per direction N/E/S/W, each an unsigned 64-bit integer** [D sonar.md:9]. A second
  `SONAR` in the same direction in the same turn overwrites the first; "only the last one is sent" [D sonar.md:26,
  protocol.md:121]. That overwrite applies only to **your own output in this turn**. It cannot touch another dragon's
  ray (see §3, jamming).
- **When it is cast:** after the action, and only if the dragon survived, in the order N, E, S, W [D sonar.md:9,
  execution-order.md:65-67]. A death on any step of a sprint drops the turn's sonar [D execution-order.md:53]. The ray
  leaves from the **post-move** head, so after a sprint it starts where the dragon ended.
- **Path:** straight line, wraps around the board, passes through portals, and stops at the **first kelp edge or
  dragon segment, own body included**. It is lost after `WIDTH + HEIGHT` tiles with no hit [D sonar.md:9]. Measured: 0%
  of top-team rays were lost; in practice every ray hits kelp or a body [M].
- **Total internal refraction:** a ray sent opposite your facing leaves from the **tail**, in the direction the tail
  points away from the body [D sonar.md:24, execution-order.md:67]. A "backward" ray therefore probes from the far end
  of a long dragon, which is often outside the head's 7x7 view.
- **Cost:** sonar itself is free. CPU cost is only output bytes: a stdout write costs 2.5M points plus 4,000 per byte,
  and the helpers flush once per turn [D timeouts.md:53,62]. A full-width line `SONAR N 18446744073709551615\n` is about
  29 bytes, about 0.12M points, so 4 encrypted rays cost about 0.46M points (0.5% of the 100M budget). This holds only
  with one flush per turn. vB19 uses `setvbuf` and a single `fflush`, which is fine. A small plaintext value such as
  `SONAR N 0` costs about 0.04M.
- **Bandwidth:** 4 x 64 = 256 bits per dragon-turn, broadcast, with no addressing. The ray's own geometry decides who
  receives it.

### Receiving
- **When:** at the start of the recipient's next turn. A recipient with a **higher id** than the sender gets it **the
  same round**; a lower id gets it the next round [D sonar.md:32]. Measured: about 50% of deliveries are same-round for
  every team [M].
- **What arrives:** the raw 64-bit values only, in the order sent. There is **no sender, team or direction**. "A signal
  may be received by a dragon on either team" [D sonar.md:32]. Interception is part of the design.
- **Queens are ids 0 and 1** [D structure.md:19, CHANGES_2026-10-01.md] and so act **first** every round [D
  execution-order.md:10]. Three consequences [R]:
  1. A sighting of the enemy queen made during anyone's turn stays exact for the rest of that round, because she has
     already moved. Any receiver with a higher id than the spotter gets that exact fix this round.
  2. Our own queen receives **every** teammate's message one round late. She still reads it before the reported enemy
     moves again: she moves first next round, and the enemy has moved at most once since the sighting.
  3. The queen's own broadcasts reach every drone the same round (every drone has a higher id).
- **Newborns:** a child takes the next id, takes its first turn later the same round, and is "a brand new instance
  ... no memory of the parent" [D splitting.md:11]. A ray that hits it this round is read on its first turn.

### ECHOES
- At the start of its next turn the sender gets **five aggregate counts** over all its rays from last turn: `kelp`,
  `ally`, `ally_head`, `enemy`, `enemy_head`. A lost ray counts nothing [D sonar.md:36-46, protocol.md:41]. Echoes
  require `PROTOCOL 3` in the reply.
- **There is no distance, no direction, no length and no id.** With several rays sent, the counts cannot be split
  between them. vS4.7 called this "attribution" [L archive insights:1307-1338].
- "ally" includes your **own body** [D sonar.md table]. Self-hits are 1-7% of rays per team [M].

### Blind spots
- Vision is a 7x7 square around the head and **does not cross portals** [D vision.md]. Sonar **does** cross portals and
  the wrap [D sonar.md:9, kelp-and-portals.md:40]. The ray is therefore the only sensor that reaches past a portal,
  which is what vB19's PPROBE uses it for.
- A ray stops at the **first** body. Anything behind a friend is invisible, and an enemy body in the line intercepts
  every later message on it [D sonar.md demo text].
- The receiver can bound the sender to the 4 axis lines through the segment that was hit (portals and tail exit
  complicate this). That is weak but non-zero information for an eavesdropper [R].

---

## 2. Current use

### Our lineage
| Build | Sonar content | Evidence |
|---|---|---|
| y7_12_49 / ours on ladder (team 98, 26 games in scout_v6) | Plaintext queen gossip `0xB0C7` (x, y, len, round, id) plus QPOS `0x5155` and PPROBE `0x5057`; mostly 1 forward ray (74% of ping-turns), 4 rays late. 56% of all our words start with `0xB0C7`. | **4,734 `0xB0C7` and 149 QPOS packets landed on enemy dragons in 26 games (about 190 readable queen reports per game handed to the opponent)** [M] |
| **vB19** (`baselines/vB19/main.cpp`) | `castRadar()` (`:1833`): (1) the true queen broadcasts plaintext QPOS (her head cell, round) on **all 4 rays every turn from r100** (`:1843-1849`); (2) else an enemy-queen alert `0xEC01` on all 4 rays if seen in the last 4 rounds; (3) else a QPOS relay on all 4 rays from r300, or if the report is ≤ 6 rounds old; (4) else a single forward or portal ray: PPROBE warn `0x5057`, otherwise value 0. Echo use: `ECHO[3]+ECHO[4]` on the single forward ray marks unseen cells on that line as `radarExpire` for 5-8 rounds (`:605-613`), until r300 only. PPROBE uses the echo through a portal (`:1719-1724`, -30 for a head beyond it). | Critic (AGENT_LOG b19_review): no team bit, so self-play poisoning; enemy-queen homing dead because `distA[head]` is -1 (`:1683-1685`). b19_v5 (alert and relay on split rays) 10/20 vs vB19: null. |
| viper_b19_f1 | Same mesh, sealed with `msgauth.hpp` (24-bit SipHash tag, **12-bit plaintext sender id**, 3-bit type, 2-bit dir, 23 data bits). | AGENT_LOG f1: auth tests pass, CPU max 61.1M. Executor flagged "**relay resealing refreshes report age**". This is a real bug: a relay seals with the current round, so a stale queen position looks fresh at every hop [R, from main.cpp:1447 `m.round >= trueQueenRound`]. |
| S4.x (`archive/dead_s4x_lineage/*/gossip.hpp`) | msgauth types T_FOUNTAIN (pearl), T_QUEEN (len + cell), T_CHOKE (reserved cell), T_LANE (no-op probe); T_INTENT, T_CLAIM, T_HANDOFF and T_GIANT defined but never sent. | Pearl gossip: +37% early eating, **ladder null** (15/30 vs 16/30, Y.7.12.3). T_CHOKE: **null**, trigger almost never fired (5/8 maps byte-identical). Probe danger `wProbeDanger=1.5`: 43.8% vs 50% overall, but **Slithery 0%→50%**, while Default, Trophy and Autarky lost 25-50pp. Queen gossip (S4.7.4): did not fix Portals. Lane sonar on the champion: 22/42 neutral (Devil 6/6 earlier). Sonar replay attack / jam build 9298: 5/30 vs 4/30, **no effect**. [L ml/results.md, archive insights:1131-1500] |

### Top teams (scout_v6, new rules) [M]
Pings per dragon-turn, share of turns with any ping, rays per ping-turn, hit mix, payload. "Plaintext" means a field
decodes at a fixed bit offset in ≥ 15% of words. Random 6/7-bit matches run 1-3%, and a random word has a popcount of
32.

| Team (rating) | ping/dt (r<100 / 100-300 / ≥300) | turns w/ ping | rays | hit kelp / ally / enemy | payload |
|---|---|---|---|---|---|
| Cache me outside (2025) | 0.50 (0.07/0.39/0.83) | 17% | 1 ray 35%, 4 rays 65% | 54/44/3% | random-looking (popcount 31.8), 72% of words re-sent |
| Computers (2025) | 2.52 flat | 96% | mostly 2-3 | 43/53/3.5% | random-looking |
| Stockfish (2015) | 3.83 flat | 98% | 4 | 59/39/2.1% | **plaintext sender head x at bit 53, y at bit 46 (7-bit), 79-86%**; popcount 19.7 |
| ???????? (2008) | 1.30 (0.62/0.65/2.54) | 66% | 1 ray 66% | 53/45/2.2% | random-looking |
| Sponge (1992) | 1.29 (0.2/0.85/2.86) | 50% | 1-3, never backward | 64/35/1.3% | random-looking |
| horse (1991) | 2.92 | 97% | 3 (F, L, R; **never backward**) | 64/33/2.7% | **plaintext**: 20-bit magics `0xc1a08`/`0xa5788` (47%), **sender id 12-bit at bit 22 (66%)**, round at bit 38; type `0xa578` packs x at 22, y at 16 |
| 3.14159265 (1987) | 3.79 | 97% | 4 | 51/46/2.8% | partly structured (magic `0xa70c` 10%, round at bit 47 21%) |
| calc (1980) | 3.93 | 98% | 4 | 59/39/2.7% | random-looking ("encrypted and signed", calc WRITEUP.md:35) |
| C-- (1947) | 3.91 | 98% | 4 | 58/36/5.2% | partly structured (round at 28 18%, id at 0 13%; popcount 21.7) |
| Team SKKU (1934) | 0.60 (0.07/0.49/1.03) | 15% | 4 | 59/40/1.5% | random-looking |
| Delusion Tax (1922) | 3.35 | 84% | 4 | 53/44/3.3% | **structured**: top bits `0x9000` 28%, y at bit 6 31%, x at bit 0 16% |
| WeHaveQuizzes (1894) | 0.71 (0.49/0.54/1.30) | 18% | 4 | 61/37/1.7% | magic `0xa2b7` 41%; queen's words are all zero bits (pure radar, 1.17 pings per queen-turn) |

Cross-cutting [M]:
- **Sonar volume does not track rating.** The two 2025-rated teams sit at 0.50 and 2.52 pings/dt. Low-volume teams
  ramp up after r300 (endgame coordination, as in calc's keeper writeup).
- **Only 1.3-5.2% of rays land on an enemy.** About 95% end on kelp (43-64%) or an ally (33-53%). Opponents still
  receive about 0.03-0.11 of our words per their dragon-turn, which is about 700-1,000 words per game against a 4-ray
  team.
- **Queens ping like everyone else** (3-4 rays/turn for 4-ray teams). 2-10% of queen rays hit an enemy (Stockfish's
  queen: 27 words per game reach the opponent).
- **No replay attacks and no jamming were seen:** in 324 games, no team ever re-sent a value first sent by the
  opponent.
- **Same word on all rays:** Cache, SKKU, Delusion Tax, WHQ, ???????? and ours (92%) send the same word on every ray
  in a turn. calc, Stockfish, horse and Computers vary per ray (per-ray nonce or per-ray content).
- **Rays that reach a newborn the same round** (parent's ray hits the child in the split round): 55-62% of splits for
  4-ray teams (Stockfish, 3.14, calc, ????????), 7-16% for low-volume teams, **9% for us** [M]. This is a free channel
  into a blank process (§3.4).
- Old-rules behaviour [L archive insights:3051-3066]: after an enemy-head echo every team goes straight more and buds
  about half as often. Messages update state and never trigger a reflex; the old #1 team sent no sonar at all. That
  conclusion ("sonar is not where the gap is") was drawn under the longest-dragon tiebreak. The queen tiebreak changes
  what one message is worth (§4).

**SIGINT check on Stockfish [M]:** in 20 Stockfish games the opponent received about 989 Stockfish words per game.
79% decode to the **exact current head of the sender**, and 13.4 per game come from Stockfish's **queen**, at a median
Manhattan distance of 10 from the receiving head (52% within 10, median round 42). The receiver cannot tell queen words
from drone words directly, but every one is an enemy-head fix beyond vision.

---

## 3. Underused tactics, ranked

EV = expected effect on wins under the queen tiebreak [R unless tagged]. Effort is in lines of vB19/f1 C++. CPU is per
dragon-turn.

| # | Tactic | EV | Effort | CPU | Local validation |
|---|---|---|---|---|---|
| 1 | **Fix and harden our own queen telemetry** (msgauth v2: no plaintext sender id, age-preserving relay, combined "situation report" word) | **High (defensive)** | ~60 | <0.1M | Yes: parity run plus spoofer opponent |
| 2 | **Enemy-queen strike relay that actually homes** (fix `distA[head]=-1`, use same-round exactness) | **High** | ~25 | ~0 | Yes: panel_zig, enemy-queen kills/game |
| 3 | **Queen echo alarm with calibrated rays** (predict each ray's stop from known map + vision; attribute the leftover; kelp echo = clear-lane certificate) | Medium-high | ~60 | ~0.05M | Yes: queen death rate and causes |
| 4 | **Parent→newborn memory handoff** on the backward (tail-exit) ray | Medium | ~30 | ~0 | Yes: child eats per first 20 turns |
| 5 | **Passive reading of enemy plaintext** (online format learner; Stockfish/horse-style head fixes) | Medium vs some opponents, 0 vs others | ~80 | ~0.1M | Partly: offline on replays now; in-game only vs a mock opponent |
| 6 | **Queen heartbeat / "our queen dead" / "enemy queen dead" flags** → switch to tiebreak-2/elimination mode | Medium (rare, decisive) | ~30 (in #1's word) | 0 | Yes: scripted queen-death maps |
| 7 | **Bed-table gossip** (3 beds per word: 12-bit cell + 4-bit gap class) | Low on ladder maps, medium on unseen | ~50 | ~0 | Yes: `maps_rm_dev`, eats/dt |
| 8 | Enemy-head broadcast for head-on avoidance ("retiring" dragon's last warning) | Low-medium | ~30 | ~0 | Weak (contention metric, see insights #3) |
| 9 | Claim / lane / choke messages against drone collisions | Low ([L] T_CHOKE null, lane neutral) | ~40 | ~0 | Yes but historically null |
| 10 | Forgery / decoys / replay attacks against opponents | Low and uncertain; **legality: flag, see 3.10** | ~40 per format | ~0 | No (needs their bot) |
| 11 | Jamming / overwriting enemy messages | **Zero: not possible** | — | — | — |
| 12 | Echo-based enemy length scouting | **Zero: echoes carry no length or distance** | — | — | — |

### 3.1 Harden our telemetry (msgauth v2)
**Problem [M/R].** vB19 sends its queen's exact head on 4 rays every turn from r100, in plaintext with a fixed magic.
The old build leaked about 190 readable queen reports per game to opponents. f1 encrypts the payload but leaves the
**sender id in clear** (bits 39:28). Anyone who reads our public replays with the same offset scan used here (§5
scripts: `id12` at a fixed offset) learns that words with sender 0/1 come from our queen. The receiving dragon then
knows the queen is on an axis line through the segment that was hit. f1 also **re-seals relays with the current
round**, so a 20-round-old queen position arrives looking fresh at every hop. vB19's plaintext accepts forged QPOS with
`round <= ROUND` (`:1433-1438`). A forged fresh QPOS moves the feed sink and the -60 "landing" zone (`:1712-1716`), and a
forged EQ pulls every drone within 10 toward a ghost (`:1683`).

**Design [R]:**
- **SIV-style word:** `tag16 = PRF_K(round, type, plaintext)`, `cipher = plaintext XOR PRF_K'(round, type, tag16)`,
  `word = tag16 | type4 | cipher44`. The receiver tries round = now and now-1 (the only two possible), decrypts, and
  recomputes the tag. No plaintext sender. Keystream reuse is harmless because the tag acts as a synthetic nonce.
  4 SipHash calls per received word, about 2-4k points [U estimate], so ≤ 0.05M for a full inbox.
- **MAC size:** an attacker only gets attempts when an enemy ray lands on us, at most ~1-3k words per game [M]. With a
  2-round window, a 16-bit tag accepts about 2·3000/65536 ≈ 0.1 random forgeries per game even if every enemy word
  were a forgery attempt. 20 bits gives ≈ 0.006. Plausibility checks (cell in bounds, not kelp, length ≤ known max)
  cut this further. **16-20 tag bits is enough; 24 wastes payload.** An 8-bit hash, as discussed in the chat, would
  accept ~20+ forgeries per game against a determined spammer [R].
- **Payload, 44 bits (one "sitrep" word replaces QPOS, EQ and relay priority fights):** own-queen cell 12 + own-queen
  age 4 + own-queen length/4 4 + enemy-queen cell 12 + enemy-queen age 4 + flags 4 (own-queen-dead, enemy-queen-dead,
  enemy-queen-length bucket 2) + 4 spare. Relays **increment age** and never re-stamp it. Every payload is
  **absolute** (cells, not offsets), so a replayed word within its 2-round life only repeats a true, near-current fact.
  That makes replay harmless by construction [R].
- Fixes the b19_v5 alert-vs-relay conflict without splitting rays.

### 3.2 Enemy-queen strike relay that works
Under tiebreak 1, a dead enemy queen with our queen alive wins the game [D structure.md:19]. vB19 already sends an EQ
alert, but the homing goal is the queen's **head cell**, whose `distA` is -1 because it is occupied, so homing never
fires [L critic]. Fix: target the best free neighbour of her head, the same fix as `torusDist` feeding. Use timing: the
queen moved first this round, so for a receiver with a **higher id than the spotter** the fix is exact this round. Only
strike if `turnsToReach(fix) ≤ ceil(L/4)` free steps, plus paid steps that keep L ≥ 2. Any dragon that sees her should
send the alert on **all rays the same turn** (it costs nothing) and keep relaying with age. Measured opportunity [M]:
Stockfish's queen alone hands opponents 13 exact head fixes per game, most before r100, when she is short.

### 3.3 Queen echo alarm (calibrated rays, clear-lane certificate)
Echoes are aggregate, but most rays are **predictable**. If the first kelp edge on a ray's path is inside vision, or on
a known-map wall with no unseen cells before it, its result is known in advance: kelp, or a visible body. Subtract the
predicted counts. The remainder belongs to the one or two unpredictable rays [R]. Two uses:
- **Alarm:** `enemy_head` remaining on an unpredictable line = an enemy head somewhere on the unseen part of that line,
  within one move of a head-on. vB19 marks only the forward ray, only before r300, and the queen gets **no radar at all**
  because she sends 4 identical QPOS rays and ignores the echo. The queen can keep sending the encrypted sitrep on 4
  rays and still read the echo.
- **Clear-lane certificate:** a `kelp` echo on a line means **no dragon of either team is anywhere on it** up to that
  kelp. This matters because of the new sprint rule: at **L ≥ 13, ceil(L/4) = 4 free steps exceeds the 3-tile vision
  radius**, so a free sprint's 4th step is blind. A kelp certificate from the previous turn, if the line is unchanged,
  makes it safe [R]. The backward ray (tail exit) certifies behind a long dragon's tail, where the head cannot see.

[L] A flat sonar-danger weight hurt open/dense-bed maps (-25 to -50pp) and helped Slithery (+50pp). Restrict this to the
**queen** (safety over speed under tiebreak 1) and to blind sprint steps. Do not apply it as a global drone penalty.

### 3.4 Parent→newborn handoff
A child is a blank process with the next id, acting later the same round [D splitting.md:11]. The parent's **backward
ray leaves from its tail** [D sonar.md:24], and right after a split the tail is next to the child's body. On 4-ray teams a
parent ray reached the newborn in the split round on 55-62% of splits; ours did on 9% [M]. That team-level figure does
not show which ray did it [U: verify that the B ray is the one that hits, using `sonarPing.dir` vs facing]. One word can
carry: the sitrep (§3.1), or 3 best beds with gap class (helps `learnGap` on unseen maps), or the nearest enemy head.
Effort is small: on a split turn, choose the B ray's content.

### 3.5 Passive reading of enemy plaintext (SIGINT)
**Permitted by design:** receiving enemy words is documented behaviour [D sonar.md:32], and replays are public. Two of
the 12 top teams (Stockfish, horse) put readable positions or ids in clear. Delusion Tax and C-- show partial structure.
Formats will change, so **do not hard-code teams**. Build an **online learner** instead [R]: for each received word that
fails our MAC, test a small set of (x-offset, y-offset, width) hypotheses. Accept a hypothesis once ≥ 5 decodes agree
with ground truth: the decoded cell is a **visible enemy head**, or lies on an axis line through a segment of ours with
no visible blocker. After that, every word in that format is an enemy-head fix. Use the fixes in threat masks (queen
safety) and as hunt cues. A word decoding to a head we see that has queen id 0/1 calibrates "queen words" if the format
carries an id (horse: id at bit 22). EV is opponent-dependent; around 2/12 of today's top teams. Validate offline first
(§5, E1).

### 3.6 Heartbeat and death flags
Our queen's death changes the right policy (tiebreak 2: longest living dragon; an all-in hunt of theirs). Today drones
infer it only from silence (vB19: the QPOS age) [R]. Put `own-queen-dead` in the sitrep, set by any dragon that saw her
die or saw her cell taken. Also `enemy-queen-dead`: then we win while our queen lives, so switch to maximum queen
safety [research_new_meta/strategy.md S7].

### 3.7 Bed-table gossip
3 beds per word at a 16-bit tag (12-bit cell + 4-bit gap class each, 48 bits). On ladder maps `maps_data.hpp` already
holds the tables, so value there is ~0. Pearl gossip was +37% early eating but null on the ladder [L]. On unseen maps
(sprint/final), every process re-learns gaps from zero (plane8_opt1_review.md B(i)). Value is medium there. Do the
cheaper in-process `learnGap` fixes first, then this. Rotate content: the queen and long dragons gossip beds rarely,
drones near rich beds more often.

### 3.8 Enemy-head warnings, retiring dragons
A dragon about to die (feeding suicide, trapped) sends its full knowledge on all 4 rays before its last action. **Rays
are discarded if it dies during its own move** [D execution-order.md:53]. A deliberate SUICIDE action dies in the
action, so its sonar is probably lost too [U: check whether a suicide action counts as "died during its move"; the
docs suggest yes]. So warn **one turn before** the planned suicide. Value is low to medium.

### 3.9 Claims, lanes, chokes
[L] T_CHOKE was null (trigger never fired). Lane sonar was neutral on the champion. Old analysis: receiving a message
changes the next move by ≤ 4 points for every team. Low priority unless a specific collision cluster shows up in
`loss_report`.

### 3.10 Deception, forgery, replay attacks: legality flag
- **Docs:** nothing in `docs/` forbids sending any uint64 value or exploiting what an opponent receives. Sonar is
  explicitly team-agnostic and sender-less [D sonar.md:32]. Players discussed spoofing and replay openly in the public
  chat ("make spoof sonar that makes that bot confused", "replay attack"; battlecode_chat_transcript.md:1000, 1115-1146),
  and no organiser objection appears in that excerpt. **Not verified against any separate terms or code of conduct.**
  Ask the organisers before shipping an active attack. Passive reading (3.5) needs no permission.
- **EV:** low. Our one ladder test (9298) showed no effect (5/30 vs 4/30) [L]. No top team replays anything [M].
  Encrypted teams are immune. Plaintext teams (Stockfish, horse) would need their **semantics**, not just their
  layout, before a forged word does anything, and we do not know what their bots do with a received head position.
  Revisit only if 3.5 shows a plaintext team acting on received positions (for example, avoiding them).

### 3.11 Jamming is impossible
"Only the last one is sent" concerns one dragon's own duplicate directions [D sonar.md:26]. Inboxes **accumulate**
several words in send order [D sonar.md:32]. The only interference is **physical interception**: a body in the line
eats every later ray [D sonar.md demo]. Flooding an enemy inbox costs them only parse and MAC time (about 4k points per
word at most), which is negligible.

### 3.12 Echo length scouting is impossible
Echoes return class counts only. Length comes only from vision (segments in view) or a cooperative report.

---

## 4. Interactions with the sprint rule and the queen tiebreak

- **Free steps vs vision:** ceil(L/4) free steps [D movement.md:60]. From L ≥ 13 the free reach (4) exceeds vision (3),
  so blind steps become free. Ray certificates (3.3) are the only sensor for those cells. Hunters at L ≥ 9 (3 free
  steps) need an exact fix: same-round relays to higher ids deliver one (3.2).
- **Staleness of sightings:** a 1-round-old enemy-queen fix has uncertainty radius ceil(L_q/4) (more if she pays
  segments). Relays must carry age (f1 bug) so the receiver can widen its reach estimate by that radius.
- **Tiebreak 1 makes single facts decisive:** only 8% of top-team wins were decided by the queen tiebreak, 54% by
  elimination, and in 83% of r500 games both queens were dead [M, dataset_v6_and_bceval.md]. A queen kill is a large
  swing toward tiebreak 2 or elimination. That raises the value of 3.2 and 3.3 compared with the old-rules finding that
  sonar does not decide games.
- **Leak cost scales with queen value:** a plaintext queen position is now the most actionable word on the board
  (3.1).

---

## 5. Cheapest three experiments first

| # | Experiment | Cost | Metric | Pass |
|---|---|---|---|---|
| E1 | **Offline SIGINT + leak audit** (no games): extend `sigint.py` to (a) run the generic online learner of 3.5 on scout_v6 and (b) parse our own vB19/f1 replays from `out/` or the ladder for any field correlated with queen id/position at fixed offsets | ~1 h Python | (a) enemy-head fixes per game learned without team hard-coding; enemy-queen fixes within 10 cells per game; (b) bits of our queen identity or position recoverable | (a) ≥ 5 queen-area fixes/game vs at least 2 top teams → build 3.5; (b) any recoverable field → 3.1 is mandatory |
| E2 | **EQ homing fix + same-round strike** (3.2) on vB19/f1, `panel_zig --set live`, 2 seeds, both sides, vs vB19 | ~25 lines, one panel | enemy-queen kills per game and kill round (from replays via `dragonDeath` id 0/1); our queen deaths | kills/game up, our queen deaths not up; win rate ≥ parity |
| E3 | **Queen echo alarm with calibrated rays** (3.3, queen only) vs vB19, same panel | ~60 lines, one panel | queen death rate by r500 and cause (head-on vs body), queen length at r250/r500, CPU max | fewer queen head-on deaths at equal length; CPU max < 65M |

After these: 3.4 (handoff) on `maps_rm_dev` with child eats per first 20 turns, then 3.1's sitrep word (parity check:
identical play on seeds without enemy contact, plus a spoofer opponent built from vB19's own plaintext format to show
the before/after damage).

---

## Scripts (read-only, scratchpad; rerun with `uv run --python 3.11 python <script>`)
`C:\Users\sohan\AppData\Local\Temp\claude\c--Users-sohan-Downloads-BattleCode-BC\ae94f628-2f5a-4042-8fd4-736bc8ad446b\scratchpad\`:
`sonar_profile.py` (per-team volume, direction, hit mix, payload field scan → `sonar_profile.json`), `sonar_queen.py`
(queen pings, same-round delivery, same-word rays, our magics hitting enemies → `sonar_queen.json`), `sonar_decode.py`
and `qbits.py` (bit layouts, queen vs drone), `newborn.py` (rays reaching a newborn), `sigint.py` (exact sender-head
decodes and queen fixes received by the opponent). The scratchpad is session-local, so copy these to `tools/` if they
are needed later.
