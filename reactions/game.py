import argparse
import contextlib
import dataclasses
import datetime
import logging
import random
import time
from typing import List, Dict, Optional

import gpiozero
import simpleaudio

from reactions import (
    screen,
    button_polling,
    segment_display,
    high_score,
    states,
    sounds,
    button_lights,
    sound,
)

_ROUNDS = 5
_DEFAULT_HIGH_SCORE = datetime.timedelta(seconds=99)
_TIMEOUT_SECS = datetime.timedelta(seconds=60)
_BUTTON_DEBOUNCE_PERIOD_SECONDS = 0.050  # 50 ms
_BUTTON_POLL_TICK_PERIOD_SECONDS = 0.01
_MAIN_LOOP_TICK_PERIOD_SECONDS = 0.01
_NEW_GAME_KEY = "N"
_GAME_ABOUT_TO_START_DURATION = datetime.timedelta(seconds=3)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(unsafe_hash=True)
class _Button:
    key: str
    audio_segment: simpleaudio.WaveObject
    led: Optional[gpiozero.LED]
    rpi_button: Optional[gpiozero.Button]


def new_button(is_rpi, key, sound_, pin_led, pin_button):
    # I was getting "wave.Error: unknown format: 65534" on some of my wav files.  Some
    # mysterious comments on the internet told me to do this, which did fix it:
    # for file in $(ls -1 originals | grep wav); do
    #   sox originals/$file -b 16 -e signed-integer $file
    # done
    wave_object = simpleaudio.WaveObject.from_wave_file(str(sounds.SOUNDS_ROOT / sound_))

    if is_rpi and pin_led is not None:
        led = gpiozero.LED(pin_led)
    else:
        led = None

    if is_rpi:
        rpi_button = gpiozero.Button(pin_button, pull_up=True)
    else:
        rpi_button = None

    return _Button(
        key=key,
        audio_segment=wave_object,
        led=led,
        rpi_button=rpi_button,
    )


@dataclasses.dataclass
class Buttons:
    in_game_buttons: List[_Button]
    buttons_by_key: Dict[str, _Button]


@contextlib.contextmanager
def create_buttons(is_rpi):
    in_game_buttons = [
        new_button(is_rpi, "Q", "mixkit-boy-says-cow-1742.wav", 17, 5),
        new_button(is_rpi, "W", "mixkit-cartoon-wolf-howling-1774.wav", 27, 4),
        # new_button(is_rpi, "E", "mixkit-cowbell-sharp-hit-1743.wav", 7, 13),
        # new_button(is_rpi, "A", "mixkit-cow-moo-indoors-1749.wav", 8, 14),
        # new_button(is_rpi, "S", "mixkit-goat-baa-stutter-1771.wav", 9, 15),
        # new_button(is_rpi, "D", "mixkit-goat-single-baa-1760.wav", 10, 16),
        # new_button(is_rpi, "X", "mixkit-stallion-horse-neigh-1762.wav", 11, 17),
    ]
    new_game_button = new_button(
        is_rpi, _NEW_GAME_KEY, "mixkit-stallion-horse-neigh-1762.wav", None, 16
    )
    try:
        buttons_by_key = {button.key: button for button in in_game_buttons + [new_game_button]}
        if is_rpi:
            with button_polling.polling_thread(
                in_game_buttons + [new_game_button],
                _BUTTON_POLL_TICK_PERIOD_SECONDS,
                _BUTTON_DEBOUNCE_PERIOD_SECONDS,
            ):
                yield Buttons(in_game_buttons, buttons_by_key)
        else:
            yield Buttons(in_game_buttons, buttons_by_key)
    finally:
        for button in in_game_buttons:
            if button.rpi_button:
                button.rpi_button.close()


def shuffled_buttons(buttons: Buttons):
    while True:
        pool = buttons.in_game_buttons + buttons.in_game_buttons
        random.shuffle(pool)
        yield from pool


@dataclasses.dataclass
class Scores:
    current: datetime.timedelta
    high: datetime.timedelta


def main_loop(stdscr, is_rpi):
    with contextlib.ExitStack() as exit_stack:
        displays = exit_stack.enter_context(segment_display.displays(is_rpi))
        buttons = exit_stack.enter_context(create_buttons(is_rpi))
        background_music = exit_stack.enter_context(sound.BackgroundMusic())

        shuffled_buttons_iter = iter(shuffled_buttons(buttons))
        lights = button_lights.button_lights(buttons, is_rpi)
        scores = Scores(
            current=datetime.timedelta(),
            high=high_score.read_high_score(default_high_score=_DEFAULT_HIGH_SCORE),
        )

        win_scores, win_footer, win_main = screen.init(stdscr)
        last_tick = time.time_ns()
        state = states.NOT_STARTED
        while True:
            button_polling.check_polling_thread_alive()

            last_tick, time_elapsed = calculate_time_elapsed(last_tick)

            keys, is_exit = read_keys(stdscr)
            if is_exit:
                break

            play_sounds(buttons, keys)
            state = tick(state, scores, keys, time_elapsed, shuffled_buttons_iter)
            screen.refresh(scores, state, win_footer, win_main, win_scores)
            displays.refresh(scores, state)
            lights.refresh(state, time_elapsed)
            background_music.refresh(state)

            time.sleep(_MAIN_LOOP_TICK_PERIOD_SECONDS)


def play_sounds(buttons, keys):
    for key in keys:
        button = buttons.buttons_by_key.get(key, None)
        if button:
            sound.try_play_audio(button.audio_segment)


def calculate_time_elapsed(last_tick):
    this_tick = time.time_ns()
    time_elapsed = datetime.timedelta(microseconds=(this_tick - last_tick) / 1000)
    last_tick = this_tick
    return last_tick, time_elapsed


def read_keys(stdscr):
    keys = []
    is_exit = screen.read_keys(stdscr, keys)
    button_polling.read_keys(keys)
    return keys, is_exit


def tick(
    state, scores, keys, time_elapsed, shuffled_buttons_iter
):  # pylint: disable=too-many-return-statements
    match state:
        case states.NOT_STARTED:
            # The game hasn't started yet.  When someone hits the new game key, start a new game.
            if _NEW_GAME_KEY in keys:
                return states.GameAboutToStart(elapsed=datetime.timedelta())

        case states.GameAboutToStart(elapsed=elapsed):
            # The game is about to start.  Time elapsed ticks up until it's greater than
            # _GAME_ABOUT_TO_START_DURATION, then the game starts by choosing the first button.
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= _GAME_ABOUT_TO_START_DURATION:
                return states.WaitingOnButton(0, button=next(shuffled_buttons_iter))
            state.elapsed = new_elapsed
            return state

        case states.CoolDown(round_=round_, delay=delay, elapsed=elapsed):
            # A button has just been pressed, wait for cool down delay to end before choosing a new
            # target button.  elapsed ticks up until it's greater than delay, then a new button is
            # chosen.
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= delay:
                return states.WaitingOnButton(round_, button=next(shuffled_buttons_iter))

            state.elapsed = new_elapsed
            return state

        case states.WaitingOnButton(round_=round_, button=button):
            # Waiting for someone to hit the right button.
            # * If the game has taken longer than _TIMEOUT_SECS then go to GameFinished.
            # * If someone managed to hit two keys at once then they are a superhuman, so don't
            #   worry about this and just look at the first key.
            # * If the key is wrong then add a penalty to the clock.
            # * If we've had enough rounds then save the high score and finish the game, otherwise
            #   enter CoolDown.
            scores.current += time_elapsed

            if scores.current >= _TIMEOUT_SECS:
                return states.GameFinished(last_score=scores.current)

            if keys:
                first_key = keys[0]
                if first_key != button.key:
                    scores.current += datetime.timedelta(seconds=5)
                if round_ == _ROUNDS - 1:
                    if scores.current < scores.high:
                        scores.high = scores.current
                        high_score.save_high_score(scores.high)
                    return states.GameFinished(last_score=scores.current)
                return states.cool_down(round_=round_ + 1)

        case states.GameFinished():
            # The game has finished,
            if _NEW_GAME_KEY in keys:
                return states.GameAboutToStart(elapsed=datetime.timedelta())

        case _:
            raise NotImplementedError(state)

    return state


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpi", action=argparse.BooleanOptionalAction)
    args = parser.parse_args()
    return args.rpi


def main():
    logging.basicConfig(filename="reactions.log", level=logging.INFO)
    is_rpi = parse_args()

    try:
        screen.wrapper(lambda stdscr: main_loop(stdscr, is_rpi))
    except KeyboardInterrupt:
        pass
