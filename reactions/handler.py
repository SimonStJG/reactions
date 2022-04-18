from typing import Protocol


class Handler(Protocol):
    def __enter__(self) -> "Handler":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...

    def refresh(self, state, is_state_change, scores, time_elapsed):
        ...


class StubHandler(Handler):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def refresh(self, *args, **kwargs):
        pass
