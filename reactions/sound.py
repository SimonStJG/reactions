import logging

import simpleaudio

from reactions import sounds, states

logger = logging.getLogger(__name__)


class BackgroundMusic:
    def __init__(self):
        self.background_wave_object = simpleaudio.WaveObject.from_wave_file(
            str(sounds.SOUNDS_ROOT / "Farm-background-noise.wav")
        )
        self.game_finished_wave_object = simpleaudio.WaveObject.from_wave_file(
            str(sounds.SOUNDS_ROOT / "sadtrombone.swf.wav")
        )
        self.play_object = None
        # TODO this is really silly, should have a proper event loop where my handlers register to
        #  receive ticks, and the ticks have sensible information like what the last state change
        #  was.
        self.is_finished = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def refresh(self, state):
        match state:
            case states.GameAboutToStart():
                self.play()
                self.is_finished = False
            case states.CoolDown():
                self.play()
                self.is_finished = False
            case states.WaitingOnButton():
                self.play()
                self.is_finished = False
            case states.GameFinished():
                if not self.is_finished:
                    try_play_audio(self.game_finished_wave_object)
                self.is_finished = True
            case _:
                self.stop()
                self.is_finished = False

    def play(self):
        logger.info(self.play_object)
        if self.play_object:
            if not self.play_object.is_playing():
                # Stopped for some reason, repeat
                self.play_object = try_play_audio(self.background_wave_object)
        else:
            self.play_object = try_play_audio(self.background_wave_object)

    def stop(self):
        if self.play_object:
            if self.play_object.is_playing():
                self.play_object.stop()
            self.play_object = None


def try_play_audio(wave_object):
    try:
        return wave_object.play()
    except Exception as exception:
        # This is bonkers, but Simpleaudioerror doesn't seem to be exported, I don't know what
        # these error codes even mean, and who cares this is just a bit of fun.
        if "CODE: -16 -- MSG: Device or resource busy" in str(
            exception
        ) or "CODE: -111 -- MSG: Connection refused" in str(exception):
            logger.warning("Simple audio is unhappy", exc_info=True)
            return None

        raise
