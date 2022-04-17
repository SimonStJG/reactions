import math

import tm1637

from reactions import states


class Displays:
    def __init__(self, current, high_score):
        self.current = current
        self.high_score = high_score

    def refresh(self, scores, state):
        match state:
            case states.NOT_STARTED:
                self.current.clear()
            case states.GameFinished:
                self.current.clear()
            case _:
                self.current.write_score(scores.current)

        self.high_score.write_score(scores.high)


class StubDisplays:
    def refresh(self, *args, **kwargs):
        pass


class Display:
    def __init__(self, device):
        self.device = device
        self.state = None

    def clear(self):
        if self.state is not None:
            self.device.write([0, 0, 0, 0])
            self.state = None

    def write_score(self, score):
        secs = min(score.seconds, 99)
        centi_secs = math.floor(score.microseconds / 10_000)
        self.write_numbers(secs, centi_secs)

    def write_numbers(self, secs, centi_secs):
        if self.state != ("numbers", secs, centi_secs):
            self.device.numbers(secs, centi_secs)
            self.state = ("numbers", secs, centi_secs)


def displays(is_rpi):
    if is_rpi:
        return Displays(Display(tm1637.TM1637(21, 20)), Display(tm1637.TM1637(19, 26)))
    return StubDisplays()
