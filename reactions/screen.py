import curses
import curses.ascii
import math

from reactions import states

WIN_COLS = 80
WIN_LINES = 20


def format_score(score):
    return f"{score.seconds:02d}:{math.floor(score.microseconds / 10_000):02}"


def validate_screen_size():
    if (
        curses.COLS < WIN_COLS  # pylint: disable=no-member
        or curses.LINES < WIN_LINES  # pylint: disable=no-member
    ):
        raise ValueError("You need at least 80 cols and 20 lines on your terminal")


def init(stdscr):
    stdscr.clear()
    # Don't block when calling getch or getstr methods.
    stdscr.nodelay(True)
    # Set the time to wait for an escape sequence after the ESC key is pressed to a tiny value.
    # We don't need any escape sequences want to use ESC to signal that the game is over.
    curses.set_escdelay(10)
    # Remove flashing cursor
    curses.curs_set(0)
    validate_screen_size()

    # Create some windows to hold the different bits of text on the screen.  win_scores is the top
    # line and has current and high score, win_footer is the bottom line and has some constant
    # text, and win_main has everything else.
    win_scores = curses.newwin(1, WIN_COLS, 0, 0)
    win_footer = curses.newwin(1, WIN_COLS, WIN_LINES - 1, 0)
    win_main = curses.newwin(WIN_LINES - 2, WIN_COLS, 1, 0)

    return win_scores, win_footer, win_main


def refresh(scores, state, win_footer, win_main, win_scores):
    _refresh_win_scores(win_scores, scores)
    _refresh_win_main(win_main, state)
    _refresh_win_footer(win_footer)


def _refresh_win_footer(win_footer):
    win_footer.move(0, 0)
    win_footer.clrtoeol()
    win_footer.addstr(0, 0, "Press Escape key to exit")
    win_footer.refresh()


def _refresh_win_scores(win_scores, scores):
    win_scores.move(0, 0)
    win_scores.clrtoeol()

    win_scores.addstr(0, 0, f"{format_score(scores.current)} <- Current score")
    high_score_msg = f"High Score -> {format_score(scores.high)}"
    win_scores.addstr(0, WIN_COLS - len(high_score_msg) - 1, high_score_msg)
    win_scores.refresh()


def _refresh_win_main(win_main, state):
    y_position = math.ceil((WIN_LINES - 2) / 2)

    def centre_message(message):
        win_main.addstr(y_position, math.ceil((WIN_COLS - len(message)) / 2), message)

    win_main.move(y_position, 0)
    win_main.clrtoeol()

    match state:
        case states.NOT_STARTED:
            centre_message("Press space bar to start")
        case states.CoolDown():
            centre_message("Get Ready")
        case states.WaitingOnButton(button=button):
            centre_message(f"Press button: {button.key}")
        case states.GameFinished(last_score=last_score):
            centre_message(
                f"Your score: {format_score(last_score)}.  Press any key to play again."
            )
        case _:
            raise NotImplementedError(state)

    win_main.refresh()


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
