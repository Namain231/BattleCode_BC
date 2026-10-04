# wsl_setup result - 2026-10-02

Status: OK. All seven Nim tools build; separate judge builds and completes one normal game. Serve protocol and lockstep parity were not tested.

Read DIGEST.md, search_s3_result.md and engine_cpp_status.md. At first inspection the approved installations were already present: just 1.43.0 at /home/sohan/.local/bin/just, Nim 2.2.6 at /home/sohan/toolchains/nim-2.2.6/bin/nim, Zig 0.16.0 at /home/sohan/toolchains/zig-linux/zig. Their PATH exports already existed in ~/.profile. No downloads/reinstalls were needed; this report does not claim their earlier installation.

Cleanup: downloaded tarballs in ~/toolchains and ~/.cache/pip and ~/.cache/uv were already absent. Extracted zig-linux, nim-2.2.6, Wasmtime v27 and v49 directories exist. Nothing needed deletion; no unrelated files were deleted. No sudo/apt, shutdown, compaction or sparse change.

| Disk check | Before | After |
| --- | --- | --- |
| Get-PSDrive C free | 3.95 GiB (rounded display) | 4,027,162,624 bytes / 3.75 GiB |
| df -h / in WSL | 1007G total, 2.9G used, 953G available | 1007G total, 3.1G used, 953G available |

C: checks between builds were 3.94, 3.88 and 3.81 GiB free; never near the 1.5 GB floor. WSL virtual free space is not Windows headroom.

Build fixes:
- Root has no justfile: literal cd ~/the-loong-game && just tools-build fails No justfile found. Canonical recipes are in examples/tooling.
- tools-build initially failed gcc not found. Created ~/.local/bin/gcc invoking "$HOME/toolchains/zig-linux/zig" cc -L"$HOME/.local/lib/loong" "$@".
- Created user-level linker symlinks ~/.local/lib/loong/libz.so -> /usr/lib/x86_64-linux-gnu/libz.so.1 and libsqlite3.so -> /usr/lib/x86_64-linux-gnu/libsqlite3.so.0. First retry built gamedata/report but failed linking SQLite; second link fixed it.
- Existing libunwind headers/static library sufficed. Existing OpenSSL/SQLite/zlib runtime libraries sufficed without development-package installs.
- Selected existing Wasmtime v49.0.1 C API include and static library; build.zig does not pin a release. v49 compiled successfully; v27 untouched.
- Appended WASMTIME_INCLUDE and WASMTIME_LIB for ~/toolchains/wasmtime-v49.0.1-x86_64-linux-c-api/{include,lib} to ~/.profile; verified fresh bash -lc resolves just/nim/zig/gcc and both variables.

Successful commands (both exit 0):
```bash
cd ~/the-loong-game/examples/tooling
just tools-build
just zig-judge-build -j2 --prefix "$HOME/toolchains/zig-judge-out-serve"
```

Seven binaries under ~/the-loong-game/build/bin (19 MB total): loong-gamedata, loong-report, loong-sample-replays, loong-recover, loong-profile, loong-map-variants, loong-regenerate. Judge builds at two jobs. Its target includes serve/lockstep and does not require Nim tools.

Checkout commit 19f56e181fd290eee24e9a0b1817d56b2eb8c6e2. Local modification: harness/zig_judge/src/main.zig gains --help/-h handler listing --serve, --serve-team, --lockstep, --games and normal run. Upstream rejected --help as MissingValue and omitted modes from error usage. Gameplay code unchanged.

New judge: /home/sohan/toolchains/zig-judge-out-serve/bin/loong-judge (32 MB). SHA256 73c0def169c878960f68f6dcf166e25e31089035f80993e1491c548bd0c0555b.
Old judge untouched: /home/sohan/toolchains/zig-judge-out/bin/loong-judge; before/after SHA256 1fd357bbd81d43f32bef67e3d338c54b6a101732f1dcf2377b5e3191d519c0fc.

New --help exits 0 and lists both required modes. Normal smoke game:
```bash
J="$HOME/toolchains/zig-judge-out-serve/bin/loong-judge"
B=/mnt/c/Users/sohan/AppData/Local/unswbc/v7_5-3f1d42aa89957b8a20a9f0815f2c3696-3edcb89d85ca002f8f71711c69f2ab7d-metered.wasm
"$J" --engine "$HOME/venv/lib/python3.14/site-packages/unswbc/unswbc_engine.wasm" --timeout 60 --map /mnt/c/Users/sohan/Downloads/BattleCode_BC/maps/default.map --a "$B" --b "$B" --seed 1
```
Exit 0: A wins at 500 rounds; surviving dragons 24/3, total lengths 135/7, zero bot failures; turns 12280/5142; max points 14773016/7822227; wall time 9790 ms. No replay/pickle written.

An earlier PowerShell-piped shell script introduced CR into seed and failed InvalidCharacter before playing. Direct wsl executable arguments fixed it. PowerShell should invoke judge directly after wsl -d Ubuntu --; Git Bash requires MSYS_NO_PATHCONV=1 for /mnt paths.

Limits: no external served-policy game and no official lockstep parity test. Bundled reference remains old-rule 1.2.2; queen-era parity needs replacement reference, such as engine_cpp host adapter. Installation/build readiness is not game-rule fidelity.

WSL help explicitly lists --manage and --set-sparse, -s <true|false>. Command available to run later after coordinating running jobs:
```powershell
wsl --manage Ubuntu --set-sparse true
```
NOT executed. CLI support confirmed from help; no claim that existing VHD space was reclaimed.
