import abc
import datetime
import random

from reactions import handler, states

ZERO_TIME_DELTA = datetime.timedelta()
FLICKER_PERIOD = datetime.timedelta(milliseconds=500)


class ButtonLights(handler.Handler):
    def __init__(self, buttons):
        self.buttons = buttons
        self.strategy = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def refresh(self, state, is_state_change, time_elapsed):
        if is_state_change or self.strategy is None:
            match state:
                case states.WaitingOnButton(button=waited_on_button):
                    self.strategy = SingleLightStrategy(self.buttons, waited_on_button)
                case states.GameAboutToStart():
                    self.strategy = LightsOffStrategy(self.buttons)
                case states.CoolDown():
                    self.strategy = LightsOffStrategy(self.buttons)
                case states.NotStarted():
                    self.strategy = FlickerStrategy(self.buttons, FLICKER_PERIOD)
                case states.GameFinishedCoolDown():
                    self.strategy = LightsOnStrategy(self.buttons)
                case states.GameFinished():
                    self.strategy = FlickerStrategy(self.buttons, FLICKER_PERIOD)
                case _:
                    raise NotImplementedError()

        self.strategy.refresh(time_elapsed)


class Strategy(abc.ABC):
    @abc.abstractmethod
    def refresh(self, time_elapsed):
        raise NotImplementedError()


class FlickerStrategy(Strategy):
    def __init__(self, buttons, period):
        self.buttons = buttons
        self.period = period
        self.delay = ZERO_TIME_DELTA

    def refresh(self, time_elapsed):
        self.delay -= time_elapsed
        if self.delay <= ZERO_TIME_DELTA:
            self.delay = self.period
            for button in self.buttons.in_game_buttons:
                if random.randint(0, 1):
                    button.led.on()
                else:
                    button.led.off()


class SingleLightStrategy(Strategy):
    def __init__(self, buttons, led_on_button):
        self.buttons = buttons
        self.led_on_button = led_on_button
        self.finished = False

    def refresh(self, time_elapsed):
        if self.finished:
            return

        for button in self.buttons.in_game_buttons:
            if button == self.led_on_button:
                button.led.on()
            else:
                button.led.off()

        self.finished = True


class LightsOffStrategy(Strategy):
    def __init__(self, buttons):
        self.buttons = buttons
        self.finished = False

    def refresh(self, time_elapsed):
        if self.finished:
            return

        for button in self.buttons.in_game_buttons:
            button.led.off()

        self.finished = True


class LightsOnStrategy(Strategy):
    def __init__(self, buttons):
        self.buttons = buttons
        self.finished = False

    def refresh(self, time_elapsed):
        if self.finished:
            return

        for button in self.buttons.in_game_buttons:
            button.led.on()

        self.finished = True


def button_lights(buttons, is_rpi):
    if is_rpi:
        return ButtonLights(buttons)
    return handler.StubHandler()
