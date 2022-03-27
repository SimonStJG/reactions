import dataclasses
import datetime
import random


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


def cool_down(round_):
    return CoolDown(
        round_=round_,
        delay=datetime.timedelta(seconds=random.randint(2000, 4000) / 1_000),
        elapsed=datetime.timedelta(),
    )
