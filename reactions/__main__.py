"""Test your reaction speed on a silly game with large buttons and ridiculous noises

TODO
* KEY_RESIZE
* ESC and ESC delay
* Sound
* Timeout at 100 secs
"""
import asyncio
import curses
import curses.ascii
import dataclasses
import datetime
import math
import random
import time

_WIN_COLS = 80
_WIN_LINES = 20
_ROUNDS = 5

_BUTTONS = {
    0: "q",
    1: "w",
    2: "e",
    3: "a",
    4: "s",
    5: "d",
    6: "x",
}


# todo move onto the state?
@dataclasses.dataclass
class Scores:
    current: datetime.timedelta = datetime.timedelta()
    high: datetime.timedelta = datetime.timedelta(minutes=1)


class State:
    NOT_STARTED = "NOT_STARTED"

    @dataclasses.dataclass()
    class CoolDown:
        round_: int
        delay: datetime.timedelta
        elapsed: datetime.timedelta

    @dataclasses.dataclass()
    class WaitingOnButton:
        round_: int
        button: str

    @dataclasses.dataclass()
    class GameFinished:
        last_score: datetime.timedelta


async def main_loop(stdscr):
    stdscr.clear()
    stdscr.nodelay(True)

    validate_screen_size()

    scores = Scores()
    win_scores = curses.newwin(1, _WIN_COLS, 0, 0)
    win_main = curses.newwin(_WIN_LINES - 1, _WIN_COLS, 1, 0)
    last_tick = time.time_ns()
    state = State.NOT_STARTED

    while True:
        last_tick, time_elapsed = await _calculate_time_elapsed(last_tick)

        keys = await read_keys(stdscr)
        state = await tick(state, scores, keys, time_elapsed)

        refresh_win_scores(win_scores, scores)
        refresh_win_main(win_main, state)

        await asyncio.sleep(0.01)


async def _calculate_time_elapsed(last_tick):
    this_tick = time.time_ns()
    time_elapsed = datetime.timedelta(microseconds=(this_tick - last_tick) / 1000)
    last_tick = this_tick
    return last_tick, time_elapsed


async def read_keys(stdscr):
    keys = []
    while True:
        key = stdscr.getch()
        if key == curses.ERR:
            break

        if key == curses.KEY_RESIZE:
            raise ValueError("TODO Handle resize")

        if key < 255:
            keys.append(chr(key))

    return keys


def refresh_win_scores(win_scores, scores):
    win_scores.erase()
    win_scores.addstr(0, 0, f"{format_score(scores.current)} <- Current score")
    high_score_msg = f"High Score -> {format_score(scores.high)}"
    win_scores.addstr(0, _WIN_COLS - len(high_score_msg) - 1, high_score_msg)
    win_scores.refresh()


def format_score(score):
    return f"{score.seconds:02d}:{math.floor(score.microseconds / 10_000):02}"


def refresh_win_main(win_main, state):
    def centre_message(message):
        win_main.addstr(
            math.ceil(_WIN_LINES / 2), math.ceil((_WIN_COLS - len(message)) / 2), message
        )

    win_main.erase()
    match state:
        case State.NOT_STARTED:
            centre_message("Press any key to start")
        case State.CoolDown():
            centre_message("Get Ready")
        case State.WaitingOnButton(button=button):
            centre_message(f"Press button: {button}")
        case State.GameFinished(last_score=last_score):
            centre_message(f"Your score: {format_score(last_score)}.  Press any key to play again.")
        case _:
            raise NotImplementedError(state)
    win_main.refresh()


async def tick(state, scores, keys, time_elapsed):
    match state:
        case State.NOT_STARTED:
            if keys:
                # TODO Dedupe
                return State.CoolDown(
                    round_=0,
                    delay=datetime.timedelta(
                        seconds=random.randint(2000, 4000) / 1_000
                    ),
                    elapsed=datetime.timedelta(),
                )

        case State.CoolDown(round_=round_, delay=delay, elapsed=elapsed):
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= delay:
                next_button = _BUTTONS[random.randrange(0, len(_BUTTONS))]
                return State.WaitingOnButton(round_, button=next_button)

            state.elapsed = new_elapsed
            return state

        case State.WaitingOnButton(round_=round_, button=button):
            scores.current += time_elapsed
            if keys:
                first_key = keys[0]
                if first_key != button:
                    scores.current += datetime.timedelta(seconds=5)
                if round_ == _ROUNDS:
                    return State.GameFinished(last_score=scores.current)
                return State.CoolDown(
                    round_=round_ + 1,
                    delay=datetime.timedelta(
                        seconds=random.randint(2000, 4000) / 1_000
                    ),
                    elapsed=datetime.timedelta(),
                )

        case State.GameFinished():
            if keys:
                State.CoolDown(
                    round_=0,
                    delay=datetime.timedelta(
                        seconds=random.randint(2000, 4000) / 1_000
                    ),
                    elapsed=datetime.timedelta(),
                )

        case _:
            raise NotImplementedError(state)

    return state


def validate_screen_size():
    if curses.COLS < _WIN_COLS or curses.LINES < _WIN_LINES:
        raise ValueError("You need at least 80 cols and 20 lines")


def main():
    curses.wrapper(lambda stdscr: asyncio.run(main_loop(stdscr)))


if __name__ == "__main__":
    main()
