import datetime
import os
import pathlib
import shutil
import tempfile


def save_file_location():
    return pathlib.Path.home() / ".reactions"


def read_high_score(default_high_score):
    location = save_file_location()
    try:
        encoded_values = location.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return default_high_score

    try:
        secs, microsecs = [int(val) for val in encoded_values.split(":")]
        return datetime.timedelta(seconds=secs, microseconds=microsecs)
    except ValueError:
        # If the file gets corrupted somehow then carry on anyway
        return default_high_score


def save_high_score(score):
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w") as temp_file_handle:
        temp_file_handle.write(str(score.seconds))
        temp_file_handle.write(":")
        temp_file_handle.write(str(score.microseconds))

        # Attempt at an atomic write
        temp_file_handle.flush()
        os.fsync(temp_file_handle.fileno())
        shutil.copy(temp_file_handle.name, save_file_location())
