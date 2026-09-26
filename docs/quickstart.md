# Quickstart

# Quickstart

For beginners, we recommend using Python to write your bots. Make sure you have Python preinstalled on your machine.

## Install the toolkit

The toolkit,unswbc, is a Python package. If you haveuv,
    install it as a tool. Upgrade later withuv tool upgrade unswbc.

```
uv tool install unswbc
```

If you do not have uv, install it with pip instead. You need Python 3.11 or newer, and the command is then called
    the same way. Should pip refuse and sayexternally-managed-environment, as Debian, Ubuntu and Homebrew
    do, install uv and use the line above.

```
pip install unswbc
```

## Check your machine

Rununswbcon its own. It lists the commands and reports what it found here: a Python interpreter, the C
    and C++ compilers, and the replay viewer. Anything missing is named with the step that installs it.

```
unswbc
```

## Create a bot

unswbc initcreates a bot project in Python, C or C++. A Python project consists ofmain.py(your bot),helper.py(the library that reads and writes the engine protocol) andbot.toml(the language and the list of files to ship). C and C++ projects containhelper.handhelper.c, orhelper.hpp, in place ofhelper.py. Maps go into amaps/folder beside the bot folder, which all your bots share.

```
unswbc init python mybot
```

After upgrading the toolkit later,unswbc mapsadds any newly bundled maps to that folder.

## Run a match

unswbc runtakes a map and two bot projects, rebuilds both bots, plays the match and writes a.replayfile. The two bots may be the same project.arena.mapis an 11×11 map to start on.

```
unswbc run maps/arena.map mybot mybot
```

## Open the replay

If you use VS Code, Cursor or VSCodium,inithas already installed the replay viewer, so clicking the.replayfile plays the match. Install it by hand if your editor arrived later.

```
unswbc vscode
```

Otherwise open thevisualiserand choose the file. Either way you see the whole board and every
    line your bots printed, neither of which a bot can see for itself.

## Log in

Make an API key on yourteam page— it starts withbc_— and hand it to the
    toolkit.unswbc auth statusthen names the team the key belongs to.

```
unswbc auth set bc_...
```

## Submit

unswbc submitzips the project and uploads it as a new version.-nnames that version and-drecords what changed. SeeSubmitting via Websitefor what happens to the
    build afterwards.

```
unswbc submit mybot
```

## Template Structure

```
import helper as unswbc

ct: unswbc.Controller
game: unswbc.Game

def execute_turn() -> None:
    ct.make_move(unswbc.Direction.NORTH)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
```

The template provides you with a game loop.init()reads the initial setup information from the engine,
    andupdate()will read in information from a new turn (or false, if the game ends or dragon dies). You
    should make changes to theexecute_turn()function, andend_turn()will finish the bot's
    turn. Advanced teams can choose to write their own interface with the engine (seeinterface docs).

The starter bot shuffles the four directions from a generator seeded the same way every run, then steps onto the
    first neighbouring tile that is not blocked by kelp or a dragon. All three starters do this, so a Python bot and a
    C++ bot behave alike. Take a look through the rest of the docs to improve this simple bot!

## Next steps

Be sure to test your bots on multiple maps! It may be useful tocreate your own mapsto
    test how your bot reacts to specific situations or edge cases. TheCLIpage lists every command
    and its options.
