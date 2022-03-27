"""Test your reaction speed on a silly game with large buttons and ridiculous noises
"""
import curses
import datetime
import math
import random
import time

_WIN_COLS = 80
_WIN_LINES = 20
_YOUR_SCORE_POS = (0, 0)
_HIGH_SCORE_POS = (0, 80 - 30)
_CENTRE_POS = (10, 40)

_BUTTONS = {
    0: "q",
    1: "w",
    2: "e",
    3: "a",
    4: "s",
    5: "d",
    6: "x",
}

_ROUNDS = 5


def main_loop(stdscr):
    stdscr.clear()

    if curses.COLS < _WIN_COLS or curses.LINES < _WIN_LINES:
        raise ValueError("You need at least 80 cols and 20 lines")
    win = curses.newwin(_WIN_LINES, _WIN_COLS, 0, 0)

    your_score = datetime.timedelta()
    high_score = datetime.timedelta(minutes=5)
    reset(win, your_score, high_score)

    while True:
        win.addstr(_CENTRE_POS[0] + 1, _CENTRE_POS[1] - 10, f"Press any key to start")
        win.refresh()
        win.getkey()
        your_score = datetime.timedelta()
        reset(win, your_score, high_score)
        _addstr_center(win, "Get Ready!!")
        win.refresh()

        for _ in range(0, _ROUNDS):
            time.sleep(random.randint(2000, 4000) / 1000)

            next_button = _BUTTONS[random.randrange(0, len(_BUTTONS))]
            reset(win, your_score, high_score)
            win.addstr(*_CENTRE_POS, f"Press {next_button}")

            clear_keys(win)

            win.refresh()
            # TODO Check which time to use
            start_time = time.time_ns()
            key = win.getkey()
            reset(win, your_score, high_score)
            time_elapsed = datetime.timedelta(microseconds= (time.time_ns() - start_time) / 1000)
            if key.lower() == next_button:
                your_score += time_elapsed
                _addstr_center(win, f"Woooooo yeah")
            else:
                your_score += time_elapsed + datetime.timedelta(minutes=1)
                _addstr_center(win, f"Oh noo :(")
            win.refresh()

        _addstr_center(win, f"Your score: {your_score}")
        high_score = min(high_score, your_score)


def clear_keys(win):
    win.nodelay(True)
    while win.getch() != -1:
        pass
    win.nodelay(False)


def _addstr_center(win, message):
    win.addstr(_CENTRE_POS[0], _CENTRE_POS[1] - math.ceil(len(message) / 2), message)


def reset(win, your_score, high_score):
    win.clear()
    win.addstr(*_YOUR_SCORE_POS, f"Your Score: {your_score}")
    win.addstr(*_HIGH_SCORE_POS, f"High Score: {high_score}")


def main():
    curses.wrapper(main_loop)


if __name__ == "__main__":
    main()
