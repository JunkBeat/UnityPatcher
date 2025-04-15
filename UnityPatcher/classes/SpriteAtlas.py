import logging
import os
import traceback

from .BaseManager import BaseManager


class SpriteAtlas(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        if len(self.data.m_PackedSprites) != len(self.data.m_PackedSpriteNamesToIndex):
            raise ValueError("Number of elements mismatch")

        new_path = path or self._get_base_dest(self.type_name, self.name)
        for i, sprite in enumerate(self.data.m_PackedSprites):
            sprite_name = self.data.m_PackedSpriteNamesToIndex[i]
            dest = self.get_destination_path(sprite_name, ".png", new_path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            try:
                img = sprite.get_obj().read().image
                img.save(dest)
            except Exception:
                logging.error(
                    "[ERR] Failed to read image in %s: %s #%d, index: %d" "\n%s",
                    self.type_name,
                    self.name,
                    self.path_id,
                    i,
                    traceback.format_exc(),
                )

    def import_(self, *args):
        raise NotImplementedError("Import is not supported")
