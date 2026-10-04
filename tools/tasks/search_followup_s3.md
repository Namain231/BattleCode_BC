# search_followup S3

Implement research-only served numpy net and sequential Python simulator search in tools/search_proto/.
Do not edit engine_cpp, baselines or shipped bots. Judge is /home/sohan/toolchains/zig-judge-out-serve/bin/loong-judge.
Ten live maps, seed 1, both seats; at most two game processes total, coordinate with S1b runner first.
M0 trivial full served game; M1 net-only 20 games; M2 depth3/two enemy samples/UCB1 20 matched games; M3 depth1 and no queen term.
Known map topology allowed; hidden starts/countdowns must never enter policy world. Unknown queen must not be rewarded as dead.
Append ASCII UTF8 log lines under search_followup, record evidence to research_new_meta/search_s3_result.md.
Verification: wsl -d Ubuntu -- /home/sohan/venv/bin/uv run --python 3.11 --with unswbc --with numpy python /mnt/c/Users/sohan/Downloads/BattleCode_BC/tools/search_proto/panel.py --engine /mnt/c/Users/sohan/AppData/Local/uv/cache/archive-v0/4Hmu77GCQL90pPgp/Lib/site-packages/unswbc/unswbc_engine.wasm --modes trivial,net,search,depth1,noqueen --jobs 2 --out /mnt/c/Users/sohan/Downloads/BattleCode_BC/out/search_followup_s3
The panel enforces the Windows disk floor, retains compact JSON game evidence, and writes no replay/pickle.
