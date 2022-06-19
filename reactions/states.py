import dataclasses
import datetime
import random


@dataclasses.dataclass
class Base:
    high_score: datetime.timedelta


@dataclasses.dataclass
class NotStarted(Base):
    pass


@dataclasses.dataclass
class GameAboutToStart(Base):
    elapsed: datetime.timedelta


@dataclasses.dataclass
class CoolDown(Base):
    round_: int
    delay: datetime.timedelta
    elapsed: datetime.timedelta
    current_score: datetime.timedelta


@dataclasses.dataclass
class WaitingOnButton(Base):
    round_: int
    button: str
    current_score: datetime.timedelta


@dataclasses.dataclass
class GameFinished(Base):
    current_score: datetime.timedelta


def cool_down(round_, high_score: datetime.timedelta, current_score: datetime.timedelta):
    return CoolDown(
        round_=round_,
        delay=datetime.timedelta(seconds=random.randint(2000, 4000) / 1_000),
        elapsed=datetime.timedelta(),
        high_score=high_score,
        current_score=current_score,
    )
