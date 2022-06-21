import logging

import simpleaudio

from reactions import sounds

logger = logging.getLogger(__name__)


class WaveObjects:
    def __init__(self):
        self.incorrect_button_press = simpleaudio.WaveObject.from_wave_file(
            str(sounds.SOUNDS_ROOT / "sadtrombone.swf.wav")
        )


def try_play_audio(wave_object):
    try:
        return wave_object.play()
    except Exception as exception:
        # This is bonkers, but Simpleaudioerror doesn't seem to be exported.  I also don't know
        # what these error codes even mean, and who cares this is just a bit of fun.
        if "CODE: -16 -- MSG: Device or resource busy" in str(
            exception
        ) or "CODE: -111 -- MSG: Connection refused" in str(exception):
            logger.warning("Simple audio is unhappy", exc_info=True)
            return None

        raise
