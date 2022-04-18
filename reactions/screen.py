import curses
import curses.ascii
import math

from reactions import states, handler

WIN_COLS = 80
WIN_LINES = 20


class Screen(handler.Handler):
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.win_scores = None
        self.win_footer = None
        self.win_main = None

    def __enter__(self):
        self.stdscr.clear()
        # Don't block when calling getch or getstr methods.
        self.stdscr.nodelay(True)
        # Set the time to wait for an escape sequence after the ESC key is pressed to a tiny value.
        # We don't need any escape sequences want to use ESC to signal that the game is over.
        curses.set_escdelay(10)
        # Remove flashing cursor
        curses.curs_set(0)
        validate_screen_size()

        # Create some windows to hold the different bits of text on the screen.  win_scores is the
        # top line and has current and high score, win_footer is the bottom line and has some
        # constant text, and win_main has everything else.
        self.win_scores = curses.newwin(1, WIN_COLS, 0, 0)
        self.win_footer = curses.newwin(1, WIN_COLS, WIN_LINES - 1, 0)
        self.win_main = curses.newwin(WIN_LINES - 2, WIN_COLS, 1, 0)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def refresh(self, state, is_state_change, scores, time_elapsed):
        self._refresh_win_scores(scores)
        self._refresh_win_main(state)
        self._refresh_win_footer()

    def _refresh_win_footer(self):
        self.win_footer.move(0, 0)
        self.win_footer.clrtoeol()
        self.win_footer.addstr(0, 0, "Press Escape key to exit")
        self.win_footer.refresh()

    def _refresh_win_scores(self, scores):
        self.win_scores.move(0, 0)
        self.win_scores.clrtoeol()

        self.win_scores.addstr(0, 0, f"{format_score(scores.current)} <- Current score")
        high_score_msg = f"High Score -> {format_score(scores.high)}"
        self.win_scores.addstr(0, WIN_COLS - len(high_score_msg) - 1, high_score_msg)
        self.win_scores.refresh()

    def _refresh_win_main(self, state):
        y_position = math.ceil((WIN_LINES - 2) / 2)

        def centre_message(message):
            self.win_main.addstr(y_position, math.ceil((WIN_COLS - len(message)) / 2), message)

        self.win_main.move(y_position, 0)
        self.win_main.clrtoeol()

        match state:
            case states.NotStarted():
                centre_message("Press N to start")
            case states.GameAboutToStart():
                centre_message("Get Ready...")
            case states.CoolDown():
                centre_message("Get Ready..")
            case states.WaitingOnButton(button=button):
                centre_message(f"Press button: {button.key}")
            case states.GameFinished(last_score=last_score):
                centre_message(f"Your score: {format_score(last_score)}.  Press N to play again.")
            case _:
                raise NotImplementedError(state)

        self.win_main.refresh()


def read_keys(stdscr, keys):
    is_exit = False

    # Read keys from keyboard
    while True:
        key = stdscr.getch()

        # No key was pressed
        if key == curses.ERR:
            break

        if key == curses.ascii.ESC:
            is_exit = True

        # I only care about the alphanumeric keys.  I'm sure there is a better way to do this but
        # whatever.
        if key < 255:
            # Nothing here cares about upper or lowercase, so just use upper everywhere
            keys.append(chr(key).upper())
    return is_exit


wrapper = curses.wrapper


def format_score(score):
    return f"{score.seconds:02d}:{math.floor(score.microseconds / 10_000):02}"


def validate_screen_size():
    if (
        curses.COLS < WIN_COLS  # pylint: disable=no-member
        or curses.LINES < WIN_LINES  # pylint: disable=no-member
    ):
        raise ValueError("You need at least 80 cols and 20 lines on your terminal")
