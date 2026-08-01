"""
Nirmana solitaire play helper.

No AI and no screenshots: you tell it what's on the 12-pit ring once, at the
start of a game (or whenever a resync is needed), and from then on it deduces
every following board itself from the move it told you to play, using the
same deterministic rules the solver uses to pick moves. That running state is
saved to nirmana_state.json, so quitting and relaunching resumes where you
left off without re-entering anything.

Pits are numbered clockwise starting from whichever pit you pick as your own
index 0. It doesn't matter which physical pit that is, as long as you count
clockwise around the ring from there and stay consistent between reads.
"""

import json
import os

import nirmana_solver


HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "nirmana_state.json")

SEARCH_DEPTH = int(os.environ.get("NIRMANA_DEPTH", str(nirmana_solver.DEFAULT_DEPTH)))

# The in-game board is always a ring of 12 pits, so this isn't configurable.
PIT_COUNT = 12


def load_state():
    """Load the persisted board state from disk, or None if there isn't one."""
    if not os.path.exists(STATE_PATH):
        return None

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            state = json.load(handle)

        return state["seeds"], state["score"], state["peril"]
    except (OSError, ValueError, KeyError):
        return None


def save_state(seeds, score, peril):
    """Persist the current board state so the next turn or run can pick it up
    without asking you to re-enter the board."""
    state = {
        "seeds": seeds,
        "score": score,
        "peril": peril,
    }

    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def clear_state():
    """Remove the saved state, e.g. once the board is cleared or won."""
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


def prompt_int(message, default):
    """Ask for an integer, returning default on a blank answer."""
    while True:
        answer = input(message).strip()

        if answer == "":
            return default

        try:
            return int(answer)
        except ValueError:
            print("Please enter a whole number.")


def prompt_seed_counts():
    """Ask for all 12 pits' seed counts, space separated, clockwise from index 0."""
    while True:
        answer = input(
            "Enter the seed count for each of the 12 pits, space separated. "
            "Pick any pit as index 0, then read clockwise around the ring from "
            "there (e.g. 3 0 1 2 0 0 4 0 0 0 2 1): "
        ).strip()

        try:
            counts = [int(token) for token in answer.split()]
        except ValueError:
            print("Please enter whole numbers only, separated by spaces.")
            continue

        if len(counts) != PIT_COUNT:
            print("That's {} numbers, but the ring has 12 pits. Try again.".format(
                len(counts)
            ))
            continue

        return counts


def prompt_yes_no(message, default):
    """Ask a yes/no question, returning default on a blank answer."""
    suffix = "Y/n" if default else "y/N"
    answer = input("{} [{}]: ".format(message, suffix)).strip().lower()

    if answer == "":
        return default

    return answer.startswith("y")


def obtain_board():
    """Ask for the whole board state fresh: the 12 seed counts, score, peril."""
    seeds = prompt_seed_counts()

    score = prompt_int(
        "What number does the SCORE dial in the center show right now? [Enter for 0]: ",
        default=0,
    )

    peril = prompt_yes_no(
        "Is the board currently in peril (the center dial flashes red)?",
        default=False,
    )

    return seeds, score, peril


def print_board(seeds, score, peril):
    print()
    print("Board (clockwise from your index 0):")

    for index, count in enumerate(seeds):
        print("  index {:>2}  {} seeds".format(index, count))

    print("  score: {}".format(score))
    print("  peril: {}".format("YES, one more 0-score turn loses" if peril else "no"))


def announce_move(seeds, peril, recommendation):
    print()

    if recommendation is None:
        print("The board is empty. You have cleared it. Well played.")
        return

    source = recommendation.source

    print("=" * 52)
    print("PLAY: index {} (it has {} seeds).".format(source, seeds[source]))
    print("This turn scores: +{}".format(recommendation.gained))

    if recommendation.cleared:
        cleared_labels = ", ".join(str(i) for i in recommendation.cleared)
        print("It clears the pit(s) at index: {}".format(cleared_labels))

    if recommendation.gained == 0:
        if peril:
            print("DANGER: no move scores, so this loses the game. Playing the least bad move.")
        elif not recommendation.any_scoring_move:
            print("No move scores this turn. Every move enters peril, this is the least bad one.")
        else:
            print("Note: this move scores nothing and puts you in peril next turn.")
    elif peril:
        print("This scores, so it lifts you out of peril.")

    print("=" * 52)


TURN_PROMPT = (
    "\nPress Enter once you've played that move, "
    "'edit' to re-enter the board (if the state looks wrong), "
    "or 'q' to quit: "
)


def play_loop():
    print("Nirmana solitaire helper ready. No AI, no screenshots: just tell it the board.")

    saved = load_state()

    if saved is not None:
        answer = input(
            "\nFound a saved game in progress. Press Enter to resume it, "
            "or type 'n' to start a new game: "
        ).strip().lower()

        if answer == "n":
            saved = None

    if saved is not None:
        seeds, score, peril = saved
    else:
        seeds, score, peril = obtain_board()
        save_state(seeds, score, peril)

    while True:
        print_board(seeds, score, peril)

        if nirmana_solver.is_cleared(seeds):
            print("\nThe board is empty. You have cleared it. Well played.")
            clear_state()
            return

        recommendation = nirmana_solver.best_move(seeds, in_peril=peril, depth=SEARCH_DEPTH)

        announce_move(seeds, peril, recommendation)

        answer = input(TURN_PROMPT).strip().lower()

        if answer == "q":
            print("Goodbye. Your progress is saved, run again to resume.")
            return

        if answer == "edit":
            seeds, score, peril = obtain_board()
            save_state(seeds, score, peril)
            continue

        # Deduce the next state from memory: the solver already computed
        # exactly what the board looks like after this move, so there's no
        # need to ask again.
        seeds = recommendation.result_pits
        score = score + recommendation.gained
        peril = recommendation.peril_after

        save_state(seeds, score, peril)


def main():
    try:
        play_loop()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye.")


if __name__ == "__main__":
    main()
