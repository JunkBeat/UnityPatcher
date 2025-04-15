from core.Settings import Settings
from utils import lock

from .BaseManager import BaseManager


class VideoClip(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        if self.data.m_VideoData:
            dest = self.get_destination_path(self.name, ".mp4", path)
            super().save(dest, self.data.m_VideoData)

    def import_(self, video_file: str):
        self.data.set_video(
            video_file,
            transcode=Settings.transcode_video,
            preset=Settings.transcode_quality,
        )
        self.save_data()

    def save_data(self):
        with lock:
            self.data.save_via_tree(Settings.resource_append_mode)
