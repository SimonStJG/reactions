import logging

import pydub
import pydub.playback

from reactions import sounds

_VOLUME_ADJUST = 12
logger = logging.getLogger(__name__)


def load_audio_segment(filename):
    return pydub.AudioSegment.from_wav(str(sounds.SOUNDS_ROOT / filename)) + _VOLUME_ADJUST


class WaveObjects:
    def __init__(self):
        self.incorrect_button_press = load_audio_segment("nasty-chord.wav")
        self.game_over = load_audio_segment("success-chord.wav")


def try_play_audio(audio_segment):
    try:
        # Not sure why this isn't public API.
        # pylint: disable=protected-access
        return pydub.playback._play_with_simpleaudio(audio_segment)
    except Exception as exception:
        # This is bonkers, but Simpleaudioerror doesn't seem to be exported.  I also don't know
        # what these error codes even mean, and who cares this is just a bit of fun.
        if "CODE: -16 -- MSG: Device or resource busy" in str(
            exception
        ) or "CODE: -111 -- MSG: Connection refused" in str(exception):
            logger.warning("Simple audio is unhappy", exc_info=True)
            return None

        raise
