# Submitting

# Submitting via website

Bots are submitted as a zip atSubmissions, or with the cli commandunswbc submit. One build at a time isactiveand plays against other teams. You must
    join ateambefore submitting.

## Submission layout

Upload your submission as a zip folder containing all the bot files. The config filebot.tomlis required at the top level, see below for the contents for each language. The size limit is 4
    MB, and you may make 12 submissions per hour. You can change the active submission an unlimited number of times.

```
[project]
language = "py"
include = [ "*.py" ]
```

## States

| State | Meaning |
| Processing | Building. |
| Ready | Built, not playing. |
| Active | Built and playing ranked matches. |
| Build failed | Did not compile, or the zip was formatted incorrectly. |

A version goes active as soon as it builds, replacing the one before it. Any Ready build can be activated, and
    earlier builds remain listed, so reverting is one click.

## Build failures

Confirm thatbot.tomlis at the top level of the zip, that the language on the form matches it, and
    thatincludelists every file, the helper included. Then unzip the archive into an empty directory and run a
    match from there; if that fails, the server's build fails for the same reason. If it still fails, ask onDiscordand quote the version number.
