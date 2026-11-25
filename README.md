# Fix Forward

A live product-management simulation. One Python server, one browser console per team.

## Run the game

Python 3.10 or newer, standard library only. No Node and no internet are needed.

```powershell
uv run python server.py --teams 3 --seconds-per-day 0.2 --new-game
```

The server prints the admin password and each team's code, and starts paused. Teams open `http://<server address>:8000/` and enter their code. Plain `python3 server.py` works the same way.

## Tests

```powershell
uv run python -m unittest discover -s tests
npm --prefix web run test
npm --prefix web run typecheck
```

## Change the console

The console source is in `web/` (Vite, React, TypeScript, Tailwind, shadcn/ui). Node 20 or newer is needed on the machine where you edit it, and nowhere else.

```powershell
npm --prefix web install
npm --prefix web run build
```

The build writes `static/`, which the server serves and which **is committed**. Rebuild and commit `static/` together with any change under `web/`, so every laptop that clones the repo runs the same console. For live editing, run `npm --prefix web run dev`; it proxies `/api` to a server on port 8000.

## Debrief on the projector

After the operator triggers the final reveal on the admin screen, the projector shows four views, switched with the number keys on the projector laptop: 1 ranking by valuation, 2 hidden-debt curves for the week-26 leader, the final winner and the biggest collapse, 3 each of those teams' error rate with the CTO's light week by week, 4 the hidden target gains of AI Copilot, Partner marketplace API and AI meeting summaries. Before the reveal none of this is available.

## When something breaks (operator runbook)

Never add `--new-game` while recovering: it moves the saved game aside and starts a new one. Every command below keeps the game. The server always comes back **paused**; resume it from the admin screen.

| What happened | What to run | Takes |
| :--- | :--- | :--- |
| The server process died or the laptop rebooted | On the same laptop: `python server.py --state-dir state --admin-password <same> --stakeholder-password <same>` | Seconds: 0.4 to 0.8 s to answer on a small log, 2.4 s on a 16-team full-length log |
| The primary laptop is dead | On the spare, stop `replicate.py`, give the spare the primary's address (organiser's step, see below), then run the same command as above | Seconds, plus the address change |
| The log is gone but a snapshot file survives | `python server.py --state-dir state --from-snapshot <snapshot file> [--registry <teams.json>]` | Seconds. Team charts start at the snapshot's day |
| The router was pulled or Wi-Fi dropped | Nothing on the server. Consoles show a connection banner and recover on their own when the network returns | None |

Use the same admin and stakeholder passwords as the dead server, or the screens will ask for new ones. Team codes come with the saved game, so teams keep their codes.

**Spare laptop.** Before the event, on the spare, run this and leave it running. It copies the log, the team registry and the newest snapshot every 5 seconds, so a takeover loses at most the last 5 seconds of actions.

```powershell
python replicate.py --primary <primary address>:8000 --admin-password <admin password> --state-dir state
```

If it prints `STOPPED: ... differ`, the primary was restarted from a snapshot or began a new game. Start the copy again in a fresh `--state-dir`. Taking over the primary's network address depends on the router, which the organiser sets up after the Wi-Fi test: give the primary a fixed address, or reserve it for the spare's hardware address, and write the step on the runbook card.

**Prove it.** Both scripts start real server processes and exit non-zero on any failure:

```powershell
python drill.py                       # kills, spare takeover, bare-snapshot start, full-length log
python loadtest.py                    # 16 teams, 20 consoles polling every 3 s, one game day per second (about 7 minutes)
python loadtest.py --full-length      # the event's pace, about 90 minutes
```

Measured on the build laptop, 25 November 2026:

| Check | Result | Bar |
| :--- | :--- | :--- |
| Hard kill mid-quarter, inside a checkpoint break, mid action burst | Back in 0.4 to 0.8 s, no acknowledged action lost, no day lost | 5 minutes |
| Spare started from the follower's copy | Back in 0.5 s, nothing lost older than the last pull | 5 minutes |
| Start from a bare snapshot after deleting the log | Back in 0.5 s, carried on 28 days | 5 minutes |
| Rebuild of a 16-team log to day 360 | 2.4 s | 1 minute |
| Load: 16 teams and 20 consoles, 11,890 requests, one full game | 0 errors, p99 under 70 ms for every kind of request, clock ticks p95 within 6% of target | 0 errors, p99 under 1 s, ticks within 25% |

## Where things are

- `fix_forward_build_spec_v3.md`: the game design. `DECISIONS.md`: why it is that way, and every build decision.
- `config.py`: every game number. `engine.py`: the pure simulation. `bots.py` and `calibrate.py`: balance testing.
- `server.py`, `game.py`, `clock.py`, `store.py`: the server, clock, event log and snapshots.
- `replicate.py`, `drill.py`, `loadtest.py`: the spare laptop follower, the failure drill and the load test.
- `docs/plans/`: the plan for each build stage.
