# Eternal Solitaire Helper

A turn-by-turn move advisor for the solitaire minigame built into **[U.V.S. Nirmana](https://store.steampowered.com/app/2536720/UVS_Nirmana/)**, the engineering puzzle game by Coincidence (the *Kaizen: A Factory Story* team), published by Klei Entertainment. Nirmana's solitaire is an [Oware](https://en.wikipedia.org/wiki/Oware)-style pit-sowing game: sow seeds around a ring of pits, clear pits that land on 2 or 3, and chain cascades for bigger scores.

No AI, no screenshots, no API key. You type in the board once, and this tool tells you the best pit to play. Pure Python standard library, no dependencies to install.

## How it works

1. You look at the board and type in how many seeds are in each pit, going clockwise starting from whichever pit you decide is index 0. It doesn't matter which physical pit you pick as 0, only that you count clockwise from there and stay consistent.
2. The tool runs a deterministic search over the game's exact rules and tells you which pit to play and what it will score.
3. You play that move in the game, then press Enter. The tool deduces the resulting board itself from the same rules it used to pick the move, no need to look at the screen again.
4. Repeat until the board is empty. Progress is saved to `nirmana_state.json` between turns and between runs, so you can quit and resume later. If the saved state ever drifts from what's actually on screen, type `edit` at any turn to re-enter the board.

## Running it

**Windows:** double-click `nirmana_helper.bat`.

**Any OS:** `python3 nirmana_helper.py`

No install step and no dependencies: everything is standard library.

## The rules it plays by

- Goal: clear every pit while maximizing score.
- Pick a non-empty pit, take its seeds, sow one per pit clockwise around the ring (wrapping past the start).
- If the last seed lands in a pit that then holds exactly 2 or 3 seeds, clear it and score that count (2 or 3).
- Then sweep counter-clockwise: each next pit that holds exactly 2 or 3 seeds is also cleared, scoring the count squared (4 or 9). The sweep stops at the first pit that isn't 2 or 3.
- A turn that scores 0 puts you in peril. Score 0 again while in peril and you lose.
- Win by clearing the whole board.

These were transcribed from the in-game tutorial. The tool always shows the board it's tracking before recommending a move, so if the game ever resolves a move differently than expected, it'll be obvious, and the fix lives in one place: `apply_move` in `nirmana_solver.py`.

## Files

- `nirmana_helper.bat` / `nirmana_helper.ps1` — double-click launchers (Windows).
- `nirmana_helper.py` — driver: prompts you for the board, then loops turn to turn.
- `nirmana_solver.py` — deterministic game rules and move search. Also runnable standalone.
- `nirmana_state.json` — saved board state between turns and runs (created at runtime, not checked in).

## Tuning

Set the `NIRMANA_DEPTH` environment variable to change how many moves ahead the solver searches (default 6). Higher plays a bit stronger but takes longer per turn.

## Testing the solver by itself

```
python nirmana_solver.py --test
python nirmana_solver.py "[3,1,1,1,0,0,0,0,0,0,0,0]"
```

## License

MIT, see [LICENSE](LICENSE).
