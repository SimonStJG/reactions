import collections
import contextlib
import logging
import threading
import time
from typing import Optional

_RPI_KEY_PRESSES = []
_RPI_KEY_PRESSES_LOCK = threading.RLock()
_BUTTON_POLL_THREAD: Optional[threading.Thread] = None
_BUTTON_POLL_THREAD_EXIT = threading.Event()

logger = logging.getLogger(__name__)


def read_keys(keys):
    with _acquire_rpi_key_presses():
        for key in _RPI_KEY_PRESSES:
            keys.append(key)
        _RPI_KEY_PRESSES.clear()


@contextlib.contextmanager
def polling_thread(buttons, tick_period_seconds, debounce_period_seconds):
    # pylint: disable=global-statement
    global _BUTTON_POLL_THREAD

    _BUTTON_POLL_THREAD = threading.Thread(
        target=_polling_thread_target,
        kwargs={
            "buttons": buttons,
            "tick_period_seconds": tick_period_seconds,
            "debounce_period_seconds": debounce_period_seconds,
        },
    )
    _BUTTON_POLL_THREAD.start()

    try:
        yield
    finally:
        _BUTTON_POLL_THREAD_EXIT.set()
        _BUTTON_POLL_THREAD.join(timeout=tick_period_seconds * 5)
        if _BUTTON_POLL_THREAD.is_alive():
            logger.error("Button poll thread didn't shutdown")


@contextlib.contextmanager
def _acquire_rpi_key_presses():
    did_acquire = _RPI_KEY_PRESSES_LOCK.acquire(blocking=True, timeout=0.01)
    if not did_acquire:
        raise ValueError("Unable to acquire lock")
    try:
        yield
    finally:
        _RPI_KEY_PRESSES_LOCK.release()


def _polling_thread_target(buttons, tick_period_seconds, debounce_period_seconds):
    button_state = collections.namedtuple("button_state", ["value", "delay"])
    logger.info("Button poll loop start")
    try:
        states = {button.key: button_state(0, 0) for button in buttons}
        last_tick = time.time()
        while not _BUTTON_POLL_THREAD_EXIT.is_set():
            now = time.time()
            time_elapsed = now - last_tick

            for button in buttons:
                (state, delay) = states[button.key]
                delay = max(0, delay - time_elapsed)
                if button.rpi_button.value != state and delay == 0:
                    logger.info("Button state change %s->%s", state, button.rpi_button.value)
                    states[button.key] = button_state(
                        button.rpi_button.value, debounce_period_seconds
                    )

                    match button.rpi_button.value:
                        case 0:
                            pass
                        case 1:
                            with _acquire_rpi_key_presses():
                                _RPI_KEY_PRESSES.append(button.key)
                        case _:
                            raise NotImplementedError()
                else:
                    states[button.key] = button_state(state, delay)

            last_tick = now
            time.sleep(tick_period_seconds)
    except:
        logger.exception("Button poll thread died")
        raise


def check_polling_thread_alive():
    if _BUTTON_POLL_THREAD and not _BUTTON_POLL_THREAD.is_alive():
        raise ValueError("Button poll thread died")
