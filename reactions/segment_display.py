import dataclasses
import math
from typing import Optional

import tm1637

from reactions import states


@dataclasses.dataclass
class Displays:
    current: Optional[tm1637.TM1637]
    high_score: Optional[tm1637.TM1637]


def get_displays(is_rpi):
    if is_rpi:
        return Displays(tm1637.TM1637(21, 20), tm1637.TM1637(19, 26))
    return None


def refresh(displays, scores, state):
    if displays:
        match state:
            case states.NOT_STARTED:
                _clear_segment_display(displays.current)
            case states.GameFinished:
                _clear_segment_display(displays.current)
            case _:
                _refresh_segment_display(scores.current, displays.current)

        _refresh_segment_display(scores.high, displays.high_score)


def _refresh_segment_display(score, display):
    secs = min(score.seconds, 99)
    centi_secs = math.floor(score.microseconds / 10_000)
    display.numbers(secs, centi_secs)


def _clear_segment_display(display):
    display.write([0, 0, 0, 0])
