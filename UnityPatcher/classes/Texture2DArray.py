import os
from typing import List

from core.Settings import Settings
from utils import lock

from .BaseManager import BaseManager


class Texture2DArray(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        new_path = path or self._get_base_dest(self.type_name, self.name)
        for i, image in enumerate(self.data.images):
            dest = self.get_destination_path(self.name, f"_{i}.png", new_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            image.save(dest)

    def import_(self, paths_to_images: List[str]):
        raw_mode = Settings.dont_compress_texture
        quality = Settings.texture_compression_quality
        generate_mips = Settings.generate_mipmaps

        if generate_mips:
            mips_count = getattr(self.data, "m_MipCount", 1)
        else:
            mips_count = 1

        self.data.set_images(
            paths_to_images, raw_mode, quality, mipmap_count=mips_count
        )
        self.save_data()

    def save_data(self):
        with lock:
            self.data.save_via_tree()
