"""
Tkinter GUI for the Nirmana solitaire helper.

Draws the 12-pit ring the way it looks on screen in the game, with a center
score dial, and highlights the recommended pit directly on the board instead
of printing a pit index. Reuses the exact same rules and search as the CLI
(nirmana_solver.py) and the same nirmana_state.json save file as the CLI
(nirmana_helper.py), so you can switch between the two mid-game.

Tkinter ships with the standard Python install on Windows and macOS. On
Linux you may need to install it separately (e.g. `sudo apt install
python3-tk`), everything else stays dependency-free.
"""

import math
import tkinter as tk
from tkinter import messagebox

import nirmana_helper
import nirmana_solver


PIT_COUNT = nirmana_helper.PIT_COUNT
SEARCH_DEPTH = nirmana_helper.SEARCH_DEPTH

CANVAS_SIZE = 640
CENTER = CANVAS_SIZE // 2
RING_RADIUS = 225
PIT_RADIUS = 40
CENTER_RADIUS = 78

COLOR_BG = "#0f211d"
COLOR_RIM = "#a6803f"
COLOR_PIT = "#241a12"
COLOR_PIT_OUTLINE = "#5a4227"
COLOR_HIGHLIGHT = "#f2c14e"
COLOR_TEXT = "#f2e6c9"
COLOR_CENTER = "#d9b56b"
COLOR_CENTER_PERIL = "#b3382c"
COLOR_CENTER_TEXT = "#3a2a12"
COLOR_PANEL_BG = "#152420"


class NirmanaGUI:
    def __init__(self, root):
        self.root = root
        root.title("Nirmana Solitaire Helper")
        root.configure(bg=COLOR_BG)
        root.resizable(False, False)

        self.pit_vars = []
        self.pit_ovals = []
        self.score_var = tk.StringVar(value="0")
        self.peril_var = tk.BooleanVar(value=False)
        self.recommendation = None

        self._build_board()
        self._build_side_panel()
        self._load_or_start_new()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_board(self):
        self.canvas = tk.Canvas(
            self.root, width=CANVAS_SIZE, height=CANVAS_SIZE,
            bg=COLOR_BG, highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, padx=14, pady=14)

        rim = RING_RADIUS + PIT_RADIUS + 32
        self.canvas.create_oval(
            CENTER - rim, CENTER - rim, CENTER + rim, CENTER + rim,
            outline=COLOR_RIM, width=3,
        )

        self.center_oval = self.canvas.create_oval(
            CENTER - CENTER_RADIUS, CENTER - CENTER_RADIUS,
            CENTER + CENTER_RADIUS, CENTER + CENTER_RADIUS,
            fill=COLOR_CENTER, outline=COLOR_RIM, width=3,
        )
        self.center_caption = self.canvas.create_text(
            CENTER, CENTER - 16, text="SCORE", fill=COLOR_CENTER_TEXT,
            font=("Segoe UI", 11, "bold"),
        )
        self.center_score_text = self.canvas.create_text(
            CENTER, CENTER + 14, text="0", fill=COLOR_CENTER_TEXT,
            font=("Segoe UI", 24, "bold"),
        )

        for index in range(PIT_COUNT):
            self._build_pit(index)

    def _build_pit(self, index):
        # The game's ring is mirrored about the vertical axis: no pit sits at
        # 12 or 6 o'clock, there are 6 pits down each side. That means the
        # pits are offset by half a step, so index 0 is the first pit
        # clockwise past 12 o'clock and you read clockwise from there.
        step = 2 * math.pi / PIT_COUNT
        angle = -math.pi / 2 + step / 2 + index * step
        x = CENTER + RING_RADIUS * math.cos(angle)
        y = CENTER + RING_RADIUS * math.sin(angle)

        oval = self.canvas.create_oval(
            x - PIT_RADIUS, y - PIT_RADIUS, x + PIT_RADIUS, y + PIT_RADIUS,
            fill=COLOR_PIT, outline=COLOR_PIT_OUTLINE, width=3,
        )
        self.pit_ovals.append(oval)

        # Push the index label straight out from the centre so it sits
        # outside the ring on every pit, instead of drifting over the board
        # on the bottom half.
        label_radius = RING_RADIUS + PIT_RADIUS + 14
        self.canvas.create_text(
            CENTER + label_radius * math.cos(angle),
            CENTER + label_radius * math.sin(angle),
            text=str(index), fill=COLOR_TEXT, font=("Segoe UI", 9),
        )

        var = tk.StringVar(value="0")
        entry = tk.Entry(
            self.canvas, textvariable=var, width=3, justify="center",
            font=("Segoe UI", 14, "bold"), bg=COLOR_PIT, fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT, relief="flat", bd=0,
        )
        entry.bind("<Return>", lambda _event: self.compute_move())
        self.canvas.create_window(x, y, window=entry)
        self.pit_vars.append(var)

    def _build_side_panel(self):
        panel = tk.Frame(self.root, bg=COLOR_BG)
        panel.grid(row=0, column=1, sticky="n", padx=(0, 16), pady=14)

        tk.Label(
            panel, text="Move advisor", bg=COLOR_BG, fg=COLOR_TEXT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        self.status = tk.Text(
            panel, width=36, height=16, bg=COLOR_PANEL_BG, fg=COLOR_TEXT,
            wrap="word", relief="flat", font=("Segoe UI", 10), padx=8, pady=8,
        )
        self.status.pack(pady=(6, 10))
        self.status.configure(state="disabled")

        tk.Checkbutton(
            panel, text="In peril (center dial flashes red)",
            variable=self.peril_var, command=self._refresh_center,
            bg=COLOR_BG, fg=COLOR_TEXT, selectcolor=COLOR_BG,
            activebackground=COLOR_BG, activeforeground=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Button(panel, text="Compute Move", command=self.compute_move).pack(
            fill="x", pady=2,
        )

        self.play_button = tk.Button(
            panel, text="Play Recommended Move", command=self.play_move,
            state="disabled",
        )
        self.play_button.pack(fill="x", pady=2)

        tk.Button(panel, text="New Game", command=self.new_game).pack(
            fill="x", pady=(12, 2),
        )

    # ------------------------------------------------------------------
    # Board state in/out
    # ------------------------------------------------------------------

    def _read_board(self):
        """Parse the 12 pit entries into ints, or None (with a dialog) if
        any of them isn't a valid non-negative whole number."""
        seeds = []

        for index, var in enumerate(self.pit_vars):
            text = var.get().strip()

            try:
                count = int(text)
            except ValueError:
                count = -1

            if count < 0:
                messagebox.showerror(
                    "Invalid pit value",
                    "Pit {} has \"{}\", which isn't a whole number of "
                    "seeds. Fix it and try again.".format(index, text),
                )
                return None

            seeds.append(count)

        return seeds

    def _write_board(self, seeds):
        for var, count in zip(self.pit_vars, seeds):
            var.set(str(count))

    def _set_score(self, score):
        self.score_var.set(str(score))
        self.canvas.itemconfigure(self.center_score_text, text=str(score))

    def _refresh_center(self):
        peril = self.peril_var.get()
        fill = COLOR_CENTER_PERIL if peril else COLOR_CENTER
        text_color = COLOR_TEXT if peril else COLOR_CENTER_TEXT

        self.canvas.itemconfigure(self.center_oval, fill=fill)
        self.canvas.itemconfigure(self.center_caption, fill=text_color, text="PERIL" if peril else "SCORE")
        self.canvas.itemconfigure(self.center_score_text, fill=text_color)

    def _clear_highlight(self):
        for oval in self.pit_ovals:
            self.canvas.itemconfigure(oval, outline=COLOR_PIT_OUTLINE, width=3)

    def _highlight_pit(self, index):
        self.canvas.itemconfigure(self.pit_ovals[index], outline=COLOR_HIGHLIGHT, width=5)

    def _log(self, lines):
        self.status.configure(state="normal")
        self.status.delete("1.0", "end")
        self.status.insert("end", "\n".join(lines))
        self.status.configure(state="disabled")

    def _save(self):
        seeds = [int(var.get()) for var in self.pit_vars]
        nirmana_helper.save_state(seeds, int(self.score_var.get()), self.peril_var.get())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_or_start_new(self):
        saved = nirmana_helper.load_state()

        if saved is not None and messagebox.askyesno(
            "Resume game?", "Found a game in progress. Resume it?"
        ):
            seeds, score, peril = saved
        else:
            seeds, score, peril = [0] * PIT_COUNT, 0, False

        self._write_board(seeds)
        self._set_score(score)
        self.peril_var.set(peril)
        self._refresh_center()
        self._clear_highlight()
        self.recommendation = None
        self.play_button.configure(state="disabled")
        self._log([
            "Type each pit's seed count on the ring (index 0 is whichever "
            "pit you choose, reading clockwise from there), then press "
            "Compute Move.",
        ])

    def compute_move(self):
        seeds = self._read_board()

        if seeds is None:
            return

        if len(seeds) != PIT_COUNT:
            messagebox.showerror("Board error", "Expected {} pits.".format(PIT_COUNT))
            return

        self._save()
        self._clear_highlight()

        if nirmana_solver.is_cleared(seeds):
            self._log(["The board is empty. You have cleared it. Well played."])
            self.recommendation = None
            self.play_button.configure(state="disabled")
            nirmana_helper.clear_state()
            return

        peril = self.peril_var.get()
        recommendation = nirmana_solver.best_move(seeds, in_peril=peril, depth=SEARCH_DEPTH)
        self.recommendation = recommendation

        self._highlight_pit(recommendation.source)
        self.play_button.configure(state="normal")

        lines = [
            "PLAY pit {} — it has {} seeds.".format(
                recommendation.source, seeds[recommendation.source]
            ),
            "",
            "Scores this turn: +{}".format(recommendation.gained),
        ]

        if recommendation.cleared:
            lines.append(
                "Clears pit(s): {}".format(
                    ", ".join(str(i) for i in recommendation.cleared)
                )
            )

        if recommendation.gained == 0:
            if peril:
                lines.append("")
                lines.append(
                    "DANGER: no move scores, so this loses the game. "
                    "This is the least-bad move."
                )
            elif not recommendation.any_scoring_move:
                lines.append("")
                lines.append(
                    "No move scores this turn. Every move enters peril, "
                    "this is the least-bad one."
                )
            else:
                lines.append("")
                lines.append("This move scores nothing and enters peril next turn.")
        elif peril:
            lines.append("")
            lines.append("This scores, so it lifts you out of peril.")

        self._log(lines)

    def play_move(self):
        if self.recommendation is None:
            return

        score = int(self.score_var.get()) + self.recommendation.gained

        self._write_board(self.recommendation.result_pits)
        self._set_score(score)
        self.peril_var.set(self.recommendation.peril_after)
        self._refresh_center()
        self._clear_highlight()

        self.recommendation = None
        self.play_button.configure(state="disabled")

        self._save()

        # Immediately line up the next move, same as the CLI's turn loop.
        self.compute_move()

    def new_game(self):
        if not messagebox.askyesno("New game", "Discard the current board and start over?"):
            return

        nirmana_helper.clear_state()
        self._write_board([0] * PIT_COUNT)
        self._set_score(0)
        self.peril_var.set(False)
        self._refresh_center()
        self._clear_highlight()
        self.recommendation = None
        self.play_button.configure(state="disabled")
        self._log(["New game. Enter the board and press Compute Move."])


def main():
    root = tk.Tk()
    NirmanaGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
