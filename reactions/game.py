import argparse
import contextlib
import dataclasses
import datetime
import logging
import logging.handlers
import math
import random
import sys
import time
from typing import Dict, List, Optional

import gpiozero
import simpleaudio

from reactions import (
    button_lights,
    button_polling,
    high_score,
    screen,
    segment_display,
    sound,
    sounds,
    states,
)

_ROUNDS = 15
_DEFAULT_HIGH_SCORE = datetime.timedelta(seconds=99)
_TIMEOUT_SECS = datetime.timedelta(seconds=60)
_BUTTON_DEBOUNCE_PERIOD_SECONDS = 0.050  # 50 ms
_BUTTON_POLL_TICK_PERIOD_SECONDS = 0.01
_MAIN_LOOP_TICK_PERIOD_SECONDS = 0.01
_NEW_GAME_KEY = "N"
_GAME_ABOUT_TO_START_DURATION = datetime.timedelta(seconds=3)
_GAME_FINISHED_COOLDOWN_DURATION = datetime.timedelta(seconds=3)
_INCORRECT_BUTTON_PRESS_PENALTY = datetime.timedelta(seconds=2)

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
        new_button(is_rpi, "Q", "mixkit-boy-says-cow-1742.wav", 13, 10),
        new_button(is_rpi, "W", "mixkit-cartoon-wolf-howling-1774.wav", 19, 22),
        new_button(is_rpi, "E", "mixkit-cowbell-sharp-hit-1743.wav", 26, 9),
        new_button(is_rpi, "A", "mixkit-cow-moo-indoors-1749.wav", 6, 17),
        new_button(is_rpi, "S", "mixkit-goat-baa-stutter-1771.wav", 5, 27),
        new_button(is_rpi, "D", "mixkit-goat-single-baa-1760.wav", 11, 4),
    ]
    new_game_button = new_button(
        is_rpi, _NEW_GAME_KEY, "mixkit-stallion-horse-neigh-1762.wav", None, 14
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


def main_loop(stdscr, is_rpi, enable_screen):  # pylint: disable=too-many-locals
    handlers = []

    with contextlib.ExitStack() as exit_stack:
        buttons = exit_stack.enter_context(create_buttons(is_rpi))
        wave_objects = sound.WaveObjects()

        def register(handler):
            handlers.append(exit_stack.enter_context(handler))

        register(screen.new_screen(stdscr, enable_screen))
        register(segment_display.displays(is_rpi))
        register(button_lights.button_lights(buttons, is_rpi))

        shuffled_buttons_iter = iter(shuffled_buttons(buttons))

        last_tick = time.time_ns()
        state = states.NotStarted(
            high_score=high_score.read_high_score(default_high_score=_DEFAULT_HIGH_SCORE)
        )
        while True:
            button_polling.check_polling_thread_alive()

            last_tick, time_elapsed = calculate_time_elapsed(last_tick)

            keys, is_exit = read_keys(stdscr)
            if is_exit:
                break

            play_sounds(buttons, keys)
            is_state_change, state = advance_state(
                state, keys, time_elapsed, shuffled_buttons_iter, wave_objects
            )

            for handler in handlers:
                handler.refresh(state, is_state_change, time_elapsed)

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
    if stdscr:
        is_exit = screen.read_keys(stdscr, keys)
    else:
        is_exit = False
    button_polling.read_keys(keys)
    return keys, is_exit


def advance_state(state, keys, time_elapsed, shuffled_buttons_iter, wave_objects):
    new_state = calculate_next_state(state, keys, time_elapsed, shuffled_buttons_iter, wave_objects)
    is_state_change = type(new_state) != type(state)  # pylint: disable=unidiomatic-typecheck

    if is_state_change:
        logger.info("State Change: %s -> %s", state, new_state)
    state = new_state
    return is_state_change, state


def calculate_next_state(
    state, keys, time_elapsed, shuffled_buttons_iter, wave_objects
):  # pylint: disable=too-many-return-statements
    match state:
        case states.NotStarted(high_score=high_score_):
            # The game hasn't started yet.  When someone hits the new game key, start a new game.
            if _NEW_GAME_KEY in keys:
                return states.GameAboutToStart(high_score=high_score_, elapsed=datetime.timedelta())

        case states.GameFinishedCoolDown(
            current_score=current_score, high_score=high_score_, elapsed=elapsed
        ):
            # The game has just finished.  Wait for enough time to elapse before entering
            # GameFinished.
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= _GAME_FINISHED_COOLDOWN_DURATION:
                return states.GameFinished(high_score=high_score_, current_score=current_score)
            state.elapsed = new_elapsed
            return state

        case states.GameFinished(high_score=high_score_):
            # The game has finished.    When someone hits the new game key, start a new game.
            if _NEW_GAME_KEY in keys:
                return states.GameAboutToStart(high_score=high_score_, elapsed=datetime.timedelta())

        case states.GameAboutToStart(high_score=high_score_, elapsed=elapsed):
            # The game is about to start.  Time elapsed ticks up until it's greater than
            # _GAME_ABOUT_TO_START_DURATION, then the game starts by choosing the first button.
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= _GAME_ABOUT_TO_START_DURATION:
                return states.WaitingOnButton(
                    high_score=high_score_,
                    round_=0,
                    button=next(shuffled_buttons_iter),
                    current_score=datetime.timedelta(),
                )
            state.elapsed = new_elapsed
            return state

        case states.CoolDown(
            high_score=high_score_,
            current_score=current_score,
            round_=round_,
            delay=delay,
            elapsed=elapsed,
        ):
            # A button has just been pressed, wait for cool down delay to end before choosing a new
            # target button.  elapsed ticks up until it's greater than delay, then a new button is
            # chosen.
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= delay:
                return states.WaitingOnButton(
                    high_score=high_score_,
                    round_=round_,
                    button=next(shuffled_buttons_iter),
                    current_score=current_score,
                )

            state.elapsed = new_elapsed
            return state

        case states.WaitingOnButton(
            high_score=high_score_, current_score=current_score, round_=round_, button=button
        ):
            # Waiting for someone to hit the right button.
            # * If the game has taken longer than _TIMEOUT_SECS then go to NotStarted (GameFinished
            #   of GameFinishedCoolDown make less sense as there is no sensible last score).
            # * If someone managed to hit two keys at once then they are a superhuman, so don't
            #   worry about this and just look at the first key.
            # * If the key is wrong then add a penalty to the current score.
            # * If we've had enough rounds then save the high score and finish the game with
            #   GameFinishedCoolDown, otherwise enter CoolDown.
            current_score = current_score + time_elapsed

            if current_score >= _TIMEOUT_SECS:
                return states.NotStarted(high_score=high_score_)

            if keys:
                first_key = keys[0]
                if first_key != button.key:
                    sound.try_play_audio(wave_objects.incorrect_button_press)
                    current_score += _INCORRECT_BUTTON_PRESS_PENALTY

                    if current_score >= _TIMEOUT_SECS:
                        return states.NotStarted(high_score=high_score_)

                if round_ == _ROUNDS - 1:
                    if current_score < high_score_:
                        high_score_ = current_score
                        high_score.save_high_score(high_score_)
                    else:
                        high_score_ = state.high_score

                    return states.GameFinishedCoolDown(
                        high_score=high_score_,
                        current_score=current_score,
                        elapsed=datetime.timedelta(),
                    )

                return cool_down(
                    high_score_=high_score_, current_score=current_score, round_=round_ + 1
                )

            state.current_score = current_score

        case _:
            raise NotImplementedError(state)

    return state


def cool_down(round_: int, high_score_: datetime.timedelta, current_score: datetime.timedelta):
    # On round 1, wait between 1.5-3 seconds and on the last round, don't wait any time at all.
    # Linearly interpolate between these.  round_ runs from 0 to max_rounds-1.
    game_progress_as_fraction = round_ / (_ROUNDS - 1)
    delay_lower_bound_ms = math.floor(1_500 * (1 - game_progress_as_fraction))
    delay_upper_bound_ms = math.floor(3_000 * (1 - game_progress_as_fraction))
    delay = datetime.timedelta(
        seconds=random.randint(delay_lower_bound_ms, delay_upper_bound_ms) / 1_000
    )
    return states.CoolDown(
        round_=round_,
        delay=delay,
        elapsed=datetime.timedelta(),
        high_score=high_score_,
        current_score=current_score,
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpi", action=argparse.BooleanOptionalAction)
    parser.add_argument("--screen", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    return args.rpi, args.screen


def main():
    is_rpi, enable_screen = parse_args()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if enable_screen:
        # Can't use the stdout handler if we're running using screen
        root_logger.addHandler(
            logging.handlers.RotatingFileHandler("reactions.log", maxBytes=10_000, backupCount=20)
        )
    else:
        root_logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    try:
        logger.info("Starting up!")
        if enable_screen:
            # Ideally this wrapper would be part of the Screen class, but that seems to be a huge
            # pain to do in practise so ¯\_(ツ)_/¯
            screen.wrapper(lambda stdscr: main_loop(stdscr, is_rpi, enable_screen))
        else:
            main_loop(None, is_rpi, enable_screen)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt", exc_info=True)
    except:
        logger.critical("Fatal error", exc_info=True)
        raise
