# Eternal Solitaire Helper

A turn-by-turn move advisor for the solitaire minigame built into **[U.V.S. Nirmana](https://store.steampowered.com/app/2536720/UVS_Nirmana/)**, the engineering puzzle game by Coincidence (the *Kaizen: A Factory Story* team), published by Klei Entertainment. The minigame is a fixed ring of 12 pits around a center score dial. It plays like [Oware](https://en.wikipedia.org/wiki/Oware): sow seeds one by one around the ring, clear pits that land on 2 or 3, and chain cascades into neighboring pits for bigger scores.

No AI, no screenshots, no API key. You type in the board once, and this tool tells you the best pit to play. Pure Python standard library, no dependencies to install. It comes in two forms that share the same save file, so you can switch between them mid-game:

- **GUI** (`nirmana_gui.py`) — a window with the ring of 12 pits drawn out like the real board. Type seed counts straight into the pits, and the recommended one lights up gold.
- **CLI** (`nirmana_helper.py`) — the same advisor as a terminal prompt, for scripting or a lighter footprint.

## How it works

1. Look at the ring of 12 pits and enter how many seeds are in each one, going clockwise starting from whichever pit you decide to call index 0. It doesn't matter which physical pit you pick as 0, only that you count clockwise from there and stay consistent between reads.
2. The tool searches the game's exact rules several moves ahead and tells you which pit to play and what it will score — in the GUI, that pit's outline turns gold; in the CLI, it's printed as a pit index.
3. Play that move in the game, then confirm it (click "Play Recommended Move" in the GUI, press Enter in the CLI). The tool works out the resulting board itself from the same rules it used to pick the move, no need to look at the screen again.
4. Repeat until the board is empty. Progress is saved to `nirmana_state.json` between turns and between runs, so you can quit and resume later, in either interface. If the saved state ever drifts from what's actually on screen, correct the pit values directly (the GUI's fields are always editable; the CLI has an `edit` command) and recompute.

## Running it

**Windows, no Python needed:** grab `eternal-solitaire-helper-gui.exe` (or `eternal-solitaire-helper.exe` for the terminal version) from the [latest release](../../releases/latest) and run it.

**From source (any OS):**

```
python3 nirmana_gui.py      # window with the ring board
python3 nirmana_helper.py   # terminal prompt
```

No install step and no dependencies: everything is standard library. The GUI needs Tk, which ships with Python on Windows and macOS; on Linux you may need to install it separately (e.g. `sudo apt install python3-tk`).

## The rules it plays by

- Goal: clear every pit while maximizing the score shown on the center dial.
- Pick a non-empty pit, take its seeds, and sow one seed per pit clockwise around the ring (wrapping past the start back to the pit you emptied).
- If the last seed you sow lands in a pit that now holds exactly 2 or 3 seeds, clear that pit and score its count (2 or 3 points).
- Then sweep counter-clockwise from there: each next pit that also holds exactly 2 or 3 seeds gets cleared too, scoring the count *squared* (4 or 9 points). The sweep stops at the first pit that isn't 2 or 3.
- A turn that scores 0 puts the board in peril (the center dial flashes red). Score 0 again while in peril and you lose.
- Win by clearing the whole board down to nothing.

These were transcribed from the in-game tutorial. The tool always shows the board it's tracking before recommending a move, so if the game ever resolves a move differently than expected, it'll be obvious, and the fix lives in one place: `apply_move` in `nirmana_solver.py`.

## Files

- `nirmana_gui.py` — Tkinter window: draws the 12-pit ring, takes seed counts as input, highlights the recommended pit.
- `nirmana_helper.py` — terminal driver: prompts you for the board, then loops turn to turn.
- `nirmana_solver.py` — deterministic game rules and move search, shared by both interfaces. Also runnable standalone.
- `nirmana_state.json` — saved board state between turns and runs, shared by both interfaces (created at runtime, not checked in).

## Tuning

Set the `NIRMANA_DEPTH` environment variable to change how many moves ahead the solver searches (default 6). Higher plays a bit stronger but takes longer per turn.

## Testing the solver by itself

```
python nirmana_solver.py --test
python nirmana_solver.py "[3,1,1,1,0,0,0,0,0,0,0,0]"
```

## License

MIT, see [LICENSE](LICENSE).
