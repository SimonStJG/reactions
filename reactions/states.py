import dataclasses
import datetime


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
class GameFinishedCoolDown(Base):
    current_score: datetime.timedelta
    elapsed: datetime.timedelta


@dataclasses.dataclass
class GameFinished(Base):
    current_score: datetime.timedelta
