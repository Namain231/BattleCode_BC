# Parameter search
Status: running; no submissions; remote lanes OFF.
Changed: tools/farm_scale.py, insights.md, AGENT_LOG.md; created tools/param_search.py, task briefs and critique.
Created: out/param_search/ps_*/ (common bot implementation, generated 12-parameter headers).
Objective: closed-start units100 + overall units100, eats/round and first-split agreement with census.
Census is winners-only; league proxies unfaithful. viper_y96qf base differs from Sv5.3 queen/sonar logic.
Command: uv run --python 3.11 --with unswbc --with scipy python -B tools/param_search.py --run
Farm command: bash tools/farm_run.sh DIR --games 2000 --search-limit LIMIT --search-stop-alpha ALPHA --search-log out/param_search.tsv -j 4
Budgets: 350, 1000, fresh 2000 games/arm; final seed offset 100000; successive halving seed 2504.
Each completed evaluation is saved by farm; TSV flushed/fsynced; search state atomic after each budget.
Early stopping: bounded paired win confidence sequence, complete balanced map cycles; family alpha split.
CPU >66M stops; chosen safety tolerance -3pp: approximate t lower CI >= -3pp, >=30 complete clusters.
Four closed-start halfway targets and other-lane critic PASS required; no auto promotion; open-map overrides fixed.
ps_00: 350 paired games; score=0.949; CPU=65.28M; eligible=False
  stripes: units100 7.0/7.0/12.5 candidate/control/top; halfway=False
  tower_defense: units100 4.0/3.0/14.5 candidate/control/top; halfway=False
  queen_of_spades: units100 7.5/7.5/12.0 candidate/control/top; halfway=False
  dilemma: units100 7.0/7.0/13.5 candidate/control/top; halfway=False
ps_01: 350 paired games; score=1.028; CPU=65.27M; eligible=False
  stripes: units100 9.0/7.0/12.5 candidate/control/top; halfway=False
  tower_defense: units100 4.0/3.0/14.5 candidate/control/top; halfway=False
  queen_of_spades: units100 9.0/7.5/12.0 candidate/control/top; halfway=False
  dilemma: units100 7.0/7.0/13.5 candidate/control/top; halfway=False
ps_02: 350 paired games; score=0.590; CPU=65.21M; eligible=False
  stripes: units100 2.0/7.0/12.5 candidate/control/top; halfway=False
  tower_defense: units100 2.0/3.0/14.5 candidate/control/top; halfway=False
  queen_of_spades: units100 5.0/7.5/12.0 candidate/control/top; halfway=False
  dilemma: units100 6.0/7.0/13.5 candidate/control/top; halfway=False
ps_03: 350 paired games; score=0.971; CPU=65.17M; eligible=False
  stripes: units100 9.5/7.0/12.5 candidate/control/top; halfway=False
  tower_defense: units100 4.0/3.0/14.5 candidate/control/top; halfway=False
  queen_of_spades: units100 6.0/7.5/12.0 candidate/control/top; halfway=False
  dilemma: units100 7.0/7.0/13.5 candidate/control/top; halfway=False
Verified: tools/buildwasm.py out/param_search/ps_00 compiled; tools/param_search_verify.py PASS (statistics/TSV/guards).
Current survivor directories: out\param_search\ps_00, out\param_search\ps_01, out\param_search\ps_02, out\param_search\ps_03
Unverified: ladder, other-lane candidate critique, acceptance criteria without full final measurements.
