import logging

import simpleaudio

from reactions import handler, sounds, states

logger = logging.getLogger(__name__)


class BackgroundMusic(handler.Handler):
    def __init__(self):
        self.background_wave_object = simpleaudio.WaveObject.from_wave_file(
            str(sounds.SOUNDS_ROOT / "Farm-background-noise.wav")
        )
        self.game_finished_wave_object = simpleaudio.WaveObject.from_wave_file(
            str(sounds.SOUNDS_ROOT / "sadtrombone.swf.wav")
        )
        self.play_object = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def refresh(self, state, is_state_change, time_elapsed):
        match state:
            case states.GameAboutToStart():
                self.play()
            case states.CoolDown():
                self.play()
            case states.WaitingOnButton():
                self.play()
            case states.GameFinished():
                self.stop()
                if is_state_change:
                    try_play_audio(self.game_finished_wave_object)
            case _:
                self.stop()

    def play(self):
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
