# The CLI

> Source: https://game.battlecode.au/docs/cli (fetched 2026-10-01, after the queen rule change)

`unswbc` creates a bot project, builds it, plays matches and uploads the result. The commands below are in the order you will need them. `unswbc help <command>` lists the options for any one of them.

## Recommended

`unswbc` is a Python package, and it carries the judge's clang, so C and C++ bots build in the sandbox with no further installing. Install [uv](https://docs.astral.sh/uv/) if you do not have it, open a new shell so it is on your PATH, then install the toolkit. Later, `uv tool install unswbc@latest` takes the newest version and `uv tool install unswbc==0.3.0` pins one. The toolkit carries the engine, so an old one plays by different rules than the judge: it asks PyPI once a day and offers to install a newer one when there is one. `UNSWBC_NO_UPDATE=1` silences that.

```
uv tool install unswbc
```

## If you don't have uv

pip installs it just as well, given Python 3.11 or newer, and puts `unswbc` on your PATH. Debian, Ubuntu and Homebrew refuse a plain pip install and say `externally-managed-environment`; on those, uv is the way.

```
pip install unswbc
```

## unswbc

On its own it lists the commands and checks this machine: the Python interpreter, the C and C++ compilers, VS Code and the replay viewer. Anything missing is named with the step that installs it.

```
unswbc
```

## unswbc init

Creates a project in `c`, `cpp` or `python`, holding a starter bot and the helper library. The directory defaults to the current one. Maps do not go inside it: they land in a `maps/` folder beside the project, which every bot of yours can share.

```
unswbc init python mybot
```

## unswbc update

Replaces a project's helper files with the ones this toolkit ships, so run it after upgrading the toolkit. Your own files are not changed, and each old helper is kept as a `.bak` file next to it. It also writes every bundled map into the `maps/` folder beside the project, replacing the ones that changed. The directory defaults to the current one. See [Protocol upgrade](/docs/protocol-upgrade).

```
unswbc update mybot
```

## unswbc maps

Adds any bundled map the folder is missing, and leaves your own files alone, so run it after upgrading the toolkit. The folder defaults to `maps`; name another to choose it, such as `unswbc maps ../maps` for a project you made in the current directory.

```
unswbc maps
```

## unswbc run

Plays one match between two bots on a map and writes a replay. Each bot is a project directory, rebuilt before it plays, and naming the same one twice plays it against itself. Add `-v` to watch every round, or `--sandbox` to run a Python, C, C++ or wasm bot the way the judge does: priced in CPU points, with its logs, indicators and drawings capped. Without it, a local match keeps all of them.

```
unswbc run maps/arena.map mybot mybot
```

## unswbc vscode

Installs the replay viewer into VS Code, Cursor or VSCodium, so any `.replay` file opens in the editor. `init` already does this when it finds one.

```
unswbc vscode
```

## unswbc auth

Stores the API key from your [team page](/team), so this machine may submit. `unswbc auth status` shows the key in use, and `unswbc auth clear` removes it.

```
unswbc auth set bc_...
```

## unswbc submit

Zips the project and uploads it as a new submission. `-n` names the version and `-d` records what changed. See [Submitting via website](/docs/submitting).

```
unswbc submit mybot
```

## unswbc log

Prints the errors the toolkit has hit on this machine. Send it with any bug report; API keys are masked.

```
unswbc log
```
