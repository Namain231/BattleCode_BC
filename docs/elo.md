# Elo

# ELO System

There is one ladder and one rating per team, starting at 1500. Every ranked battle moves both teams along it;
    unranked battles leave it alone.

## What a rating means

A rating is a prediction. Put two of them side by side and Elo turns the gap into an expected share of the battle's
    five games. Two equal teams are predicted to split them 2.5 each. A team 400 points ahead is predicted to take about
    4.5 of the 5.

When the battle finishes, what actually happened is compared with that prediction. If you outperform relative to
    your ELO, you gain rating and the other team loses it; if you fall short, you lose ELO.

This is why a rating eventually settles somewhere. If you sit above the level you actually play at, you will keep
    losing ELO until your results support where you are.

## Why a win can cost you rating

Your score in a battle is your proportion of games won, not whether you won overall. A ranked battle is five games,
    so a 3–2 win counts as 0.6, not 1.

Against a team 400 points below you, the prediction is about 4.5 games of the 5. Win 3–2 and you took 3, well short
    of what your rating claimed you would do, so rating moves to them even though you won the battle. At that gap even
    4–1 costs you, and only a 5–0 sweep gains anything.

The same rule is what makes playing upwards worth it. An underdog predicted to take half a game is already ahead of
    the prediction with one win, so a 1–4 loss gains rating.

## Examples

| Your rating | Opponent | Predicted | Result | Change | New bot |
| 1500 | 1500 | 2.5 of 5 | 3–2 | +2 | +10 |
| 1500 | 1500 | 2.5 of 5 | 5–0 | +12 | +48 |
| 1900 | 1500 | 4.5 of 5 | 3–2 | -7 | -30 |
| 1500 | 1900 | 0.5 of 5 | 2–3 | +7 | +30 |

Equal teams, won 3–2.The prediction is an even 2.5 games each, and you took
    half a game more than that, so +2 changes hands. A close battle between equals barely moves either
    of you.

Equal teams, won 5–0.The same prediction, but there was nothing left to take. That is as far past
    an even prediction as a result can get, so you collect +12, the biggest swing two equal settled
    bots can produce. A new bot would collect +48.

400 points ahead, won 3–2.Your rating predicted 4.5 games of the 5,
    and 3 is well under it. You won the battle and still paid 7 rating for it. The favourite is
    not being punished for winning; it is being charged for winning by less than it claimed it would.

400 points behind, lost 2–3.The inverse of the row above. You were predicted to take
    0.5 games, took 2, and +7 comes to you despite losing the battle.

The Change column is for a bot that has settled. A new bot moves further on the same result, shown in the last
    column; see below.

## New bots

Each submission has its own K, set by how many ranked battles it counts as having played. At 0 it is K =
    96, so a new bot can climb or drop to where it belongs in a handful of battles. K then falls evenly to K =
    24 at 10 and stays there, so once a bot has found its level, a lucky or unlucky draw of maps only
    nudges it.

A bot's count is its starting count plus the ranked battles it has played itself. The starting count is fixed when
    the bot plays its first ranked battle, by the first of these that applies:

- Same code.If your team has already played ranked with a bot of exactly the same code, the new one
        starts from that bot's count (the highest, if there are several). A re-upload never starts over.
- Second new bot within 12 hours.If another of your team's bots started from 0 in the
        last 12 hours, the new one starts from the count of the bot your team last played a ranked battle with,
        capped at 10.
- Otherwiseit starts from 0 at K = 96, and your team's 12 hours start again.

Same code means the same files with the same contents. How you zip them does not matter: timestamps, compression, a
    single folder wrapping everything, and__MACOSX,.DS_Storeand__pycache__entries are ignored. Changing any file, even a comment, makes it different code, and rule 2 then decides.

Activating an older submission again carries on from its own count. One that has never played ranked is decided by
    the rules above when it first does. Bots that played ranked before these rules came in keep counting their own
    battles from 0, and bots uploaded before them are never matched as the same code.

For example, v1 plays its first ranked battle at 9:00, starting from 0, and has played 4 by 13:00. At 13:00 you
    upload v2, which is different code, within 12 hours of v1's start, so it starts from 4 (K ≈ 67). At 14:00 you upload v1 again: same code as v1, so it starts from v1's 4 plus nothing new, still 4. From 21:00, 12
    hours after v1 started, the next bot with new code starts from 0 again.

Both teams in a battle use their own K. A new bot beating a settled one gains a lot, and the settled team loses only
    what its own K allows.

## The formula

Ratings are updated by Elo, applied once per battle rather than per game. Against a team ratedRB, a team ratedRAhas expected share 1 / (1 + 10(RB−RA) / 400). Its actual share is the fraction of the battle's games it won, with a draw counting as half. Each team's rating
    changes by its own K times the difference, rounded. K is 96 at a count of 0 (seeNew bots) and falls by 7.2 with each battle, down to
    24 from 10 on.

A battle is settled only when all of its games have finished, so a five-game series changes the rating once.
    Unranked battles do not affect ratings. The autoscrim draw is ranked, so those battles move your rating too, and
    they are most of what you play.

## Tiers

| Tier | Rating |
| Fishing Boat | 2800+ |
| Leviathan | 2500–2799 |
| Orca | 2200–2499 |
| Shark | 1900–2199 |
| Swordfish | 1600–1899 |
| Tunafish | 1300–1599 |
| Shrimp | 1000–1299 |
| Plankton | 0–999 |
