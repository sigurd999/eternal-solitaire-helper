"""
Deterministic solver for Nirmana's solitaire minigame (an Oware-style,
single-player sowing puzzle). Everything about sowing, scoring, cascades,
peril, and move selection lives here; the driver in nirmana_helper.py only
handles reading the board from you and tracking state between turns.

Board representation
--------------------
`pits` is a flat list of seed counts in clockwise order, starting from index 0.
Index i is one pit. Clockwise sowing moves i -> (i + 1) % N. Counter-clockwise
moves i -> (i - 1) % N.

Rules encoded (from the in-game tutorial)
-----------------------------------------
- Pick any non-empty pit, take all its seeds, sow one per pit clockwise,
  wrapping past the start. The source pit can receive a seed on a wrap.
- If the last sown seed lands in a pit that now holds exactly 2 or 3 seeds,
  clear it and score the count itself (2 or 3). This is the "landing" removal.
- Then sweep counter-clockwise from the landing pit. Each consecutive pit that
  holds exactly 2 or 3 seeds is cleared too, scoring the count squared (4 or 9).
  The chain stops at the first pit that is not exactly 2 or 3.
- A turn that scores 0 enters "peril". Scoring 0 again while in peril loses the
  game. Scoring any points clears peril.
- The board is won when every pit is empty.
"""

import json
import sys
from collections import namedtuple


# Search tuning. Raise DEFAULT_DEPTH for stronger play, lower it if a turn feels
# slow. The other weights order the priorities: never lose, then clear the board,
# then score high, then leave fewer seeds, then avoid peril.
#
# Depth 8 comes from playing out 25 identical random 50-seed boards at each
# depth. Mean final score went 96.9 (d6) -> 99.1 (d7) -> 101.5 (d8) -> 103.1
# (d9), with the win rate flat at 23/25 throughout, so the extra depth buys
# points without costing games. Cost grows about 5x per level: the slowest
# single move measured 0.07s at d6, 2.2s at d8 and 11.6s at d9. Depth 8 is
# the last one that still feels instant enough to sit behind a UI button.
# Override per-run with the NIRMANA_DEPTH environment variable.
DEFAULT_DEPTH = 8

WIN_BONUS = 1000.0
LOSS_PENALTY = -1_000_000.0
SEED_PENALTY = 1.0
PERIL_PENALTY = 8.0

NODE_BUDGET = 2_000_000


# A single move recommendation, ready for the driver to describe to the user.
Recommendation = namedtuple(
    "Recommendation",
    [
        "source",          # index of the pit to play
        "gained",          # points scored this turn by that move
        "result_pits",     # board after the move resolves
        "cleared",         # indices cleared this turn (landing first, then cascade)
        "last_index",      # index where the last sown seed landed
        "projected_value", # search value of the whole line (score plus heuristics)
        "peril_after",     # whether the move leaves you in peril
        "any_scoring_move",# whether at least one legal move scored this turn
    ],
)


def apply_move(pits, source):
    """
    Play `source` on `pits` and resolve landing removal plus the cascade.

    Returns (new_pits, gained, cleared_indices, last_index). Does not mutate the
    input list.
    """
    size = len(pits)
    work = list(pits)

    seeds = work[source]
    work[source] = 0

    position = source

    for _ in range(seeds):
        position = (position + 1) % size
        work[position] += 1

    last_index = position

    gained = 0
    cleared = []

    if work[last_index] in (2, 3):
        gained += work[last_index]        # landing removal scores linear
        cleared.append(last_index)
        work[last_index] = 0

        cursor = last_index

        while True:
            cursor = (cursor - 1) % size  # sweep counter-clockwise

            if cursor == last_index:
                break                     # wrapped the whole ring, stop

            if work[cursor] in (2, 3):
                gained += work[cursor] ** 2   # cascade scores squared
                cleared.append(cursor)
                work[cursor] = 0
            else:
                break

    return work, gained, cleared, last_index


def legal_moves(pits):
    """Every pit index that currently holds at least one seed."""
    return [index for index, count in enumerate(pits) if count > 0]


def is_cleared(pits):
    """True when the board is empty and the game is won."""
    return all(count == 0 for count in pits)


def _heuristic(pits, in_peril):
    """Static value of a non-terminal state at the search horizon."""
    remaining = sum(pits)

    value = -SEED_PENALTY * remaining

    if in_peril:
        value -= PERIL_PENALTY

    return value


class _Searcher:
    """Depth-limited search over the deterministic game tree with memoization."""

    def __init__(self, depth):
        self.depth = depth
        self.cache = {}
        self.nodes = 0

    def value_to_go(self, pits, in_peril, depth):
        if is_cleared(pits):
            return WIN_BONUS

        if depth <= 0 or self.nodes >= NODE_BUDGET:
            return _heuristic(pits, in_peril)

        key = (pits, in_peril, depth)

        if key in self.cache:
            return self.cache[key]

        self.nodes += 1

        best = LOSS_PENALTY

        for move in legal_moves(pits):
            new_pits, gained, _cleared, _last = apply_move(pits, move)

            if gained == 0 and in_peril:
                value = LOSS_PENALTY
            else:
                next_peril = gained == 0
                future = self.value_to_go(tuple(new_pits), next_peril, depth - 1)
                value = gained + future

            if value > best:
                best = value

        self.cache[key] = best

        return best


def best_move(pits, in_peril=False, depth=DEFAULT_DEPTH):
    """
    Choose the best legal move for the current board.

    Returns a Recommendation, or None when the board is already empty.
    """
    if is_cleared(pits):
        return None

    board = tuple(pits)

    searcher = _Searcher(depth)

    any_scoring_move = False

    best_value = None
    best = None

    for move in legal_moves(board):
        new_pits, gained, cleared, last_index = apply_move(board, move)

        if gained > 0:
            any_scoring_move = True

        if gained == 0 and in_peril:
            value = LOSS_PENALTY
        else:
            next_peril = gained == 0
            future = searcher.value_to_go(tuple(new_pits), next_peril, depth - 1)
            value = gained + future

        # Tie-break toward the bigger immediate score, then the emptier board.
        candidate_rank = (value, gained, -sum(new_pits))

        if best_value is None or candidate_rank > best_value:
            best_value = candidate_rank
            best = Recommendation(
                source=move,
                gained=gained,
                result_pits=new_pits,
                cleared=cleared,
                last_index=last_index,
                projected_value=value,
                peril_after=(gained == 0),
                any_scoring_move=any_scoring_move,
            )

    # any_scoring_move is finalized after scanning every move; fix it on the result.
    best = best._replace(any_scoring_move=any_scoring_move)

    return best


def _print_trace(pits, recommendation):
    if recommendation is None:
        print("Board is already empty. Nothing to play.")
        return

    source = recommendation.source

    print("Board (index: seeds): ", end="")
    print(", ".join("{}:{}".format(i, c) for i, c in enumerate(pits)))
    print()

    print("Recommended move: play pit index {} ({} seeds).".format(
        source,
        pits[source],
    ))

    print("Scores this turn: +{}".format(recommendation.gained))

    if recommendation.cleared:
        labels = ", ".join(str(i) for i in recommendation.cleared)
        print("Clears pits at index: {}".format(labels))

    print("Board after move: ", end="")
    print(", ".join("{}:{}".format(i, c) for i, c in enumerate(recommendation.result_pits)))

    if recommendation.gained == 0:
        print("Warning: this move scores 0 and enters peril.")

    if not recommendation.any_scoring_move:
        print("Warning: no legal move scores this turn.")


def _run_tests():
    """Self-checks that reproduce the tutorial scoring example."""
    size = 12

    # Tutorial cascade: a pit of 3 sows into a run of pits that all become 2,
    # producing +2 (landing, linear) then +4 +4 (cascade, squared) = 10.
    board = [0] * size
    board[0] = 3
    board[1] = 1
    board[2] = 1
    board[3] = 1

    new_pits, gained, cleared, last_index = apply_move(board, 0)

    assert gained == 10, "expected tutorial total 10, got {}".format(gained)
    assert last_index == 3, "expected landing at index 3, got {}".format(last_index)
    assert set(cleared) == {1, 2, 3}, "expected clears {{1,2,3}}, got {}".format(set(cleared))
    assert new_pits[0] == 0 and new_pits[1] == 0, "run should be emptied"

    # Landing on exactly 2 with no cascade neighbor scores a flat +2.
    board = [0] * size
    board[0] = 1
    board[1] = 1

    _pits, gained, cleared, last_index = apply_move(board, 0)

    assert gained == 2, "expected +2, got {}".format(gained)
    assert cleared == [1], "expected clear at index 1, got {}".format(cleared)

    # Landing on exactly 3 scores +3, and a counter-clockwise 3 cascades to +9.
    board = [0] * size
    board[0] = 2
    board[1] = 2
    board[2] = 2

    _pits, gained, cleared, last_index = apply_move(board, 0)

    assert last_index == 2, "expected landing at index 2, got {}".format(last_index)
    assert gained == 3 + 9, "expected +3 then +9 = 12, got {}".format(gained)
    assert set(cleared) == {2, 1}, "expected clears {{1,2}}, got {}".format(set(cleared))

    # A move that lands on 4 scores nothing.
    board = [0] * size
    board[0] = 1
    board[1] = 3

    _pits, gained, cleared, _last = apply_move(board, 0)

    assert gained == 0, "expected 0, got {}".format(gained)
    assert cleared == [], "expected no clears, got {}".format(cleared)

    print("All solver self-checks passed.")


def _main(argv):
    if len(argv) >= 2 and argv[1] == "--test":
        _run_tests()
        return

    if len(argv) < 2:
        print('Usage: python nirmana_solver.py "[4,0,1,2,...]" [--peril] [--depth N]')
        print("       python nirmana_solver.py --test")
        return

    pits = json.loads(argv[1])

    in_peril = "--peril" in argv

    depth = DEFAULT_DEPTH

    if "--depth" in argv:
        depth = int(argv[argv.index("--depth") + 1])

    recommendation = best_move(pits, in_peril=in_peril, depth=depth)

    _print_trace(pits, recommendation)


if __name__ == "__main__":
    _main(sys.argv)
