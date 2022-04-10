"""Test your reaction speed on a silly game with large buttons and ridiculous noises

Stuff which doesn't work / is a bit silly:
* SIGWINCH / KEY_RESIZE not delivered when terminal is resized
* The way I'm using curses can't possibly be right..  why do I have to redraw the footer??
"""
import argparse
import asyncio
import curses
import curses.ascii
import dataclasses
import datetime
import math
import os
import pathlib
import random
import shutil
import tempfile
import time
from typing import Dict, List

import gpiozero
import simpleaudio

import reactions.sounds

_WIN_COLS = 80
_WIN_LINES = 20
_ROUNDS = 5
_DEFAULT_HIGH_SCORE = datetime.timedelta(seconds=60)
_TIMEOUT_SECS = datetime.timedelta(seconds=60)


@dataclasses.dataclass
class Button:
    key: str
    audio_segment: simpleaudio.WaveObject
    led: gpiozero.LED
    rpi_button: gpiozero.Button


class StubLED:
    pass


class StubButton:
    pass


# A place to keep all of the RPi buttons which have been pressed since the last tick.
rpi_key_presses = []


def new_button(is_rpi, key, sound, pin_led, pin_button):
    # I was getting "wave.Error: unknown format: 65534" on some of my wav files.  Some
    # mysterious comments on the internet told me to do this, which did fix it:
    # for file in $(ls -1 originals | grep wav); do
    #   sox originals/$file -b 16 -e signed-integer $file
    # done
    wave_object = simpleaudio.WaveObject.from_wave_file(
        str(reactions.sounds.SOUNDS_ROOT / sound)
    )

    if is_rpi:
        led = gpiozero.LED(pin_led)
    else:
        led = StubLED()

    if is_rpi:
        rpi_button = gpiozero.Button(pin_button)
    else:
        rpi_button = StubButton()

    button = Button(
        key,
        wave_object,
        led,
        rpi_button,
    )
    if is_rpi:
        async def append_button_press():
            return rpi_key_presses.append(button)

        def when_activated():
            asyncio.run_coroutine_threadsafe(append_button_press(), asyncio.get_event_loop())

        # Ensure that it's the asyncio event loop which adds to _rpi_key_presses not the gpiozero
        # thread, otherwise we could get some concurrent modification problems.
        button.rpi_button.when_activated = when_activated

    return button


@dataclasses.dataclass
class Buttons:
    buttons: List[Button]
    buttons_by_key: Dict[str, Button]


def create_buttons(is_rpi):
    buttons = [
        new_button(is_rpi, "Q", "mixkit-boy-says-cow-1742.wav", 5, 11),
        new_button(is_rpi, "W", "mixkit-cartoon-wolf-howling-1774.wav", 6, 12),
        new_button(is_rpi, "E", "mixkit-cowbell-sharp-hit-1743.wav", 7, 13),
        new_button(is_rpi, "A", "mixkit-cow-moo-indoors-1749.wav", 8, 14),
        new_button(is_rpi, "S", "mixkit-goat-baa-stutter-1771.wav", 9, 15),
        new_button(is_rpi, "D", "mixkit-goat-single-baa-1760.wav", 10, 16),
        new_button(is_rpi, "X", "mixkit-stallion-horse-neigh-1762.wav", 11, 17),
    ]
    buttons_by_key = {button.key: button for button in buttons}
    return Buttons(buttons, buttons_by_key)


def shuffled_buttons(buttons: Buttons):
    while True:
        pool = buttons.buttons + buttons.buttons
        random.shuffle(pool)
        yield from pool


@dataclasses.dataclass
class Scores:
    current: datetime.timedelta
    high: datetime.timedelta


class State:  # pylint: disable=too-few-public-methods
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


def save_file_location():
    return pathlib.Path.home() / ".reactions"


def read_high_score():
    location = save_file_location()
    try:
        encoded_values = location.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return _DEFAULT_HIGH_SCORE

    try:
        secs, microsecs = [int(val) for val in encoded_values.split(":")]
        return datetime.timedelta(seconds=secs, microseconds=microsecs)
    except ValueError:
        # If the file gets corrupted somehow then carry on anyway
        return _DEFAULT_HIGH_SCORE


def save_high_score(score):
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w") as temp_file_handle:
        temp_file_handle.write(str(score.seconds))
        temp_file_handle.write(":")
        temp_file_handle.write(str(score.microseconds))

        # Attempt at an atomic write
        temp_file_handle.flush()
        os.fsync(temp_file_handle.fileno())
        shutil.copy(temp_file_handle.name, save_file_location())


async def main_loop(stdscr, is_rpi):
    buttons = create_buttons(is_rpi)
    shuffled_buttons_iter = iter(shuffled_buttons(buttons))
    scores = Scores(current=datetime.timedelta(), high=read_high_score())
    win_scores, win_footer, win_main = init_curses(stdscr)
    last_tick = time.time_ns()
    state = State.NOT_STARTED
    while True:
        last_tick, time_elapsed = await calculate_time_elapsed(last_tick)

        keys, is_exit = await read_keys(stdscr)
        if is_exit:
            break

        play_sounds(buttons, keys)
        state = await tick(state, scores, keys, time_elapsed, shuffled_buttons_iter)
        refresh_curses_windows(scores, state, win_footer, win_main, win_scores)

        await asyncio.sleep(0.01)


def init_curses(stdscr):
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
    win_scores = curses.newwin(1, _WIN_COLS, 0, 0)
    win_footer = curses.newwin(1, _WIN_COLS, _WIN_LINES - 1, 0)
    win_main = curses.newwin(_WIN_LINES - 2, _WIN_COLS, 1, 0)

    return win_scores, win_footer, win_main


def refresh_curses_windows(scores, state, win_footer, win_main, win_scores):
    refresh_win_scores(win_scores, scores)
    refresh_win_main(win_main, state)
    refresh_win_footer(win_footer)


def play_sounds(buttons, keys):
    for key in keys:
        button = buttons.buttons_by_key.get(key, None)
        if button:
            button.audio_segment.play()


async def calculate_time_elapsed(last_tick):
    this_tick = time.time_ns()
    time_elapsed = datetime.timedelta(microseconds=(this_tick - last_tick) / 1000)
    last_tick = this_tick
    return last_tick, time_elapsed


async def read_keys(stdscr):
    keys = []
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

    # Read keys from RPi buttons
    for button in rpi_key_presses:
        keys.append(button.key)

    return keys, is_exit


def refresh_win_footer(win_footer):
    win_footer.move(0, 0)
    win_footer.clrtoeol()
    win_footer.addstr(0, 0, "Press Escape key to exit")
    win_footer.refresh()


def refresh_win_scores(win_scores, scores):
    win_scores.move(0, 0)
    win_scores.clrtoeol()

    win_scores.addstr(0, 0, f"{format_score(scores.current)} <- Current score")
    high_score_msg = f"High Score -> {format_score(scores.high)}"
    win_scores.addstr(0, _WIN_COLS - len(high_score_msg) - 1, high_score_msg)
    win_scores.refresh()


def refresh_win_main(win_main, state):
    y_position = math.ceil((_WIN_LINES - 2) / 2)

    def centre_message(message):
        win_main.addstr(y_position, math.ceil((_WIN_COLS - len(message)) / 2), message)

    win_main.move(y_position, 0)
    win_main.clrtoeol()

    match state:
        case State.NOT_STARTED:
            centre_message("Press space bar to start")
        case State.CoolDown():
            centre_message("Get Ready")
        case State.WaitingOnButton(button=button):
            centre_message(f"Press button: {button.key}")
        case State.GameFinished(last_score=last_score):
            centre_message(
                f"Your score: {format_score(last_score)}.  Press any key to play again."
            )
        case _:
            raise NotImplementedError(state)

    win_main.refresh()


def format_score(score):
    return f"{score.seconds:02d}:{math.floor(score.microseconds / 10_000):02}"


async def tick(
    state, scores, keys, time_elapsed, shuffled_buttons_iter
):  # pylint: disable=too-many-return-statements
    match state:
        case State.NOT_STARTED:
            if " " in keys:
                return cool_down(round_=0)

        case State.CoolDown(round_=round_, delay=delay, elapsed=elapsed):
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= delay:
                return State.WaitingOnButton(round_, button=next(shuffled_buttons_iter))

            state.elapsed = new_elapsed
            return state

        case State.WaitingOnButton(round_=round_, button=button):
            scores.current += time_elapsed

            if scores.current >= _TIMEOUT_SECS:
                return State.GameFinished(last_score=scores.current)

            if keys:
                first_key = keys[0]
                if first_key != button.key:
                    scores.current += datetime.timedelta(seconds=5)
                if round_ == _ROUNDS - 1:
                    if scores.current < scores.high:
                        scores.high = scores.current
                        save_high_score(scores.high)
                    return State.GameFinished(last_score=scores.current)
                return cool_down(round_=round_ + 1)

        case State.GameFinished():
            if keys:
                scores.current = datetime.timedelta()
                return cool_down(round_=0)

        case _:
            raise NotImplementedError(state)

    return state


def cool_down(round_):
    return State.CoolDown(
        round_=round_,
        delay=datetime.timedelta(seconds=random.randint(2000, 4000) / 1_000),
        elapsed=datetime.timedelta(),
    )


def validate_screen_size():
    if (
        curses.COLS < _WIN_COLS  # pylint: disable=no-member
        or curses.LINES < _WIN_LINES  # pylint: disable=no-member
    ):
        raise ValueError("You need at least 80 cols and 20 lines on your terminal")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpi", action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    return args.rpi


def main():
    is_rpi = parse_args()

    try:
        curses.wrapper(lambda stdscr: asyncio.run(main_loop(stdscr, is_rpi)))
    except KeyboardInterrupt:
        pass

