import math

import tm1637

from reactions import states, handler


class Displays(handler.Handler):
    def __init__(self, current, high_score):
        self.current = current
        self.high_score = high_score

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.current.clear()
        self.high_score.clear()

    def refresh(self, state, is_state_change, scores, time_elapsed):
        match state:
            case states.NotStarted():
                self.current.clear()
                self.high_score.write_score(scores.high)
            case states.GameAboutToStart():
                self.current.text("GOOD")
                self.high_score.text("LUCK")
            case states.GameFinished():
                self.current.write_score(scores.current)
                self.high_score.write_score(scores.high)
            case _:
                self.current.write_score(scores.current)
                self.high_score.write_score(scores.high)

    def clear(self):
        self.current.clear()
        self.high_score.clear()


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

    def text(self, message):
        if self.state != ("text", message):
            self.device.write(self.device.encode_string(message))
            self.state = ("text", message)


def displays(is_rpi):
    if is_rpi:
        return Displays(Display(tm1637.TM1637(18, 15)), Display(tm1637.TM1637(24, 23)))

    return handler.StubHandler()
