import os

from core.Settings import Settings
from utils import lock

from .BaseManager import BaseManager


class AudioClip(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        for clip_name, clip_data in self.data.samples.items():
            name, ext = os.path.splitext(clip_name)
            dest = self.get_destination_path(name, ext, path)
            super().save(dest, clip_data)

    def import_(self, audio_path: str):
        compress_audio = not Settings.dont_compress_audio
        self.data.set_audio(audio_path, compress_audio)
        self.save_data()

    def save_data(self):
        with lock:
            self.data.save_via_tree(Settings.resource_append_mode)
