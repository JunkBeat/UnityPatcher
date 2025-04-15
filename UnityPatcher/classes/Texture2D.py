import os

from core.Settings import Settings
from utils import lock

from .BaseManager import BaseManager


class Texture2D(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        if self.data.m_CompleteImageSize > 0:
            dest = self.get_destination_path(self.name, ".png", path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                img = self.data.image
                img.save(dest)
            except Exception:
                # trying to remove image data to read using StreamData
                self.data._image_data = None
                img = self.data.image
                img.save(dest)

    def import_(self, image_file: str):
        raw_mode = Settings.dont_compress_texture
        quality = Settings.texture_compression_quality
        generate_mips = Settings.generate_mipmaps

        if generate_mips:
            mips_count = getattr(self.data, "m_MipCount", 1)
        else:
            mips_count = 1

        self.data.set_image(image_file, raw_mode, quality, mipmap_count=mips_count,
            #target_format=12 # convert to dxt5 (for test purposes only)
            #target_format=25 # convert to bc7 (for test purposes only)
        )
        self.save_data()

    def save_data(self):
        with lock:
            try:
                self.data.save_via_tree()
            except Exception:
                self.data.save()
