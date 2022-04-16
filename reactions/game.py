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

import reactions.sounds
from reactions import screen, button_polling, segment_display, high_score, states

_ROUNDS = 5
_DEFAULT_HIGH_SCORE = datetime.timedelta(seconds=99)
_TIMEOUT_SECS = datetime.timedelta(seconds=60)
_BUTTON_DEBOUNCE_PERIOD_SECONDS = 0.050  # 50 ms
_BUTTON_POLL_TICK_PERIOD_SECONDS = 0.01
_MAIN_LOOP_TICK_PERIOD_SECONDS = 0.01


@dataclasses.dataclass(unsafe_hash=True)
class _Button:
    key: str
    audio_segment: simpleaudio.WaveObject
    led: Optional[gpiozero.LED]
    rpi_button: Optional[gpiozero.Button]


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
    buttons: List[_Button]
    buttons_by_key: Dict[str, _Button]


@contextlib.contextmanager
def create_buttons(is_rpi):
    buttons = [
        new_button(is_rpi, "Q", "mixkit-boy-says-cow-1742.wav", 17, 5),
        new_button(is_rpi, "W", "mixkit-cartoon-wolf-howling-1774.wav", 27, 4),
        # new_button(is_rpi, "E", "mixkit-cowbell-sharp-hit-1743.wav", 7, 13),
        # new_button(is_rpi, "A", "mixkit-cow-moo-indoors-1749.wav", 8, 14),
        # new_button(is_rpi, "S", "mixkit-goat-baa-stutter-1771.wav", 9, 15),
        # new_button(is_rpi, "D", "mixkit-goat-single-baa-1760.wav", 10, 16),
        # new_button(is_rpi, "X", "mixkit-stallion-horse-neigh-1762.wav", 11, 17),
    ]
    try:
        buttons_by_key = {button.key: button for button in buttons}
        if is_rpi:
            with button_polling.polling_thread(
                buttons,
                _BUTTON_POLL_TICK_PERIOD_SECONDS,
                _BUTTON_DEBOUNCE_PERIOD_SECONDS,
            ):
                yield Buttons(buttons, buttons_by_key)
        else:
            yield Buttons(buttons, buttons_by_key)
    finally:
        for button in buttons:
            if button.rpi_button:
                button.rpi_button.close()


def shuffled_buttons(buttons: Buttons):
    while True:
        pool = buttons.buttons + buttons.buttons
        random.shuffle(pool)
        yield from pool


@dataclasses.dataclass
class Scores:
    current: datetime.timedelta
    high: datetime.timedelta


def main_loop(stdscr, is_rpi):
    displays = segment_display.get_displays(is_rpi)

    with create_buttons(is_rpi) as buttons:
        shuffled_buttons_iter = iter(shuffled_buttons(buttons))
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
            update_button_lights(state, buttons, is_rpi)
            state = tick(state, scores, keys, time_elapsed, shuffled_buttons_iter)
            screen.refresh(scores, state, win_footer, win_main, win_scores)
            segment_display.refresh(displays, scores, state)

            time.sleep(_MAIN_LOOP_TICK_PERIOD_SECONDS)


def play_sounds(buttons, keys):
    for key in keys:
        button = buttons.buttons_by_key.get(key, None)
        if button:
            button.audio_segment.play()


def update_button_lights(state, buttons, is_rpi):
    if not is_rpi:
        return

    match state:
        case states.WaitingOnButton(button=waited_on_button):
            for button in buttons.buttons:
                if button == waited_on_button:
                    button.led.on()
                else:
                    button.led.off()
        case _:
            for button in buttons.buttons:
                button.led.off()


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
            # TODO should be new game button
            if " " in keys:
                return states.cool_down(round_=0)

        case states.CoolDown(round_=round_, delay=delay, elapsed=elapsed):
            new_elapsed = elapsed + time_elapsed
            if new_elapsed >= delay:
                return states.WaitingOnButton(
                    round_, button=next(shuffled_buttons_iter)
                )

            state.elapsed = new_elapsed
            return state

        case states.WaitingOnButton(round_=round_, button=button):
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
            if keys:
                scores.current = datetime.timedelta()
                return states.cool_down(round_=0)

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
