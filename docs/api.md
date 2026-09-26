# Api

# API

Everything a team does on Submissions and Battles, and everything readable on the site, is available over JSON. Team
    settings, membership and accounts are changed on the site only.

## Keys

Each member makes one key onTeam. It acts as that member, so uploads and challenges are
    recorded against their name. The key is shown once. Making a new one replaces the old one, leaving the team deletes
    it, and the leader can revoke any member's key.

```
curl https://game.battlecode.au/api/v1/me \
  -H "Authorization: Bearer bc_..."
```

## Conventions

The base URL ishttps://game.battlecode.au/api/v1. Requests and responses are JSON, except the upload
    (multipart) and the two downloads. Errors carry the status and a message:

```
{ "error": "That API key is not valid. Make a new one on your team page." }
```

The limits are 120 requests a minute per key, and 30 a minute for/leaderboardand/ratings, the two expensive reads. Over either limit the response is 429 with aRetry-Afterheader. An unknown path under/api/v1is a 404 in the same shape, never an HTML page.

## You and your team

- GET /meyour user, team and key.
- GET /teamyour team with members, record, rank and pending join requests.

## Submissions

- GET /submissionsevery version with wins, draws and losses.
- POST /submissionsupload a version. Fields: name, language (python, c, cpp), description, zip. The zip
        is 4 MB at most, and a team can upload 12 versions an hour.
- GET /submissions/:idone version with its build log.
- GET /submissions/:id/downloadthe zip you uploaded.
- POST /submissions/:id/activatemake it the version that plays.

```
curl https://game.battlecode.au/api/v1/submissions \
  -H "Authorization: Bearer $KEY" \
  -F name=v12 -F language=python -F description="wider search" -F [email protected]
```

```
curl -X POST https://game.battlecode.au/api/v1/submissions/42/activate \
  -H "Authorization: Bearer $KEY"
```

## Battles

- GET /battles?limit=50your battles, newest first, up to 200.
- POST /battleschallenge a team. Body: teamId, ranked, mapIds (optional). Ranked is a five-game series.
        Same limits as the site: one pending battle per opponent, 60 games an hour.
- GET /battles/:idone battle with its games and, if unplayed, its place in the queue. For your own
        battles it also carrieslog, which says why a game crashed or timed out.
- GET /battles/:id/replaythe replay file, once the game has finished. Answers with a redirect to a
        temporary download link, so follow redirects (curl -L). The link carries its own signature, so your
        key must not be sent on to it. curl drops the header across hosts for you; some clients keep it, Python'surllibamong them, and the download is refused.

```
curl https://game.battlecode.au/api/v1/battles \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{ "teamId": 7, "ranked": false, "mapIds": [3] }'
```

```
{ "ids": [1201] }
```

```
curl -L -o 1201.replay https://game.battlecode.au/api/v1/battles/1201/replay \
  -H "Authorization: Bearer $KEY"
```

## Reads

- GET /leaderboardthe ladder as the Leaderboard page shows it: rating history, members, institutions and
        prize eligibility.
- GET /ratingsthe same ladder, ratings and history only.
- GET /teamsteams listed on Find a team.
- GET /teams/:ida team's public profile and recent battles.
- GET /tournamentsandGET /tournaments/:idtournaments and brackets.
- GET /mapsthe maps in play, with their text.
- GET /queuelive judge capacity and queue length.
