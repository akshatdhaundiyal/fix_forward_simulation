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

## Where things are

- `fix_forward_build_spec_v3.md`: the game design. `DECISIONS.md`: why it is that way, and every build decision.
- `config.py`: every game number. `engine.py`: the pure simulation. `bots.py` and `calibrate.py`: balance testing.
- `server.py`, `game.py`, `clock.py`, `store.py`: the server, clock, event log and snapshots.
- `docs/plans/`: the plan for each build stage.
