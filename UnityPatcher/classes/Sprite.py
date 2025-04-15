import os

from .BaseManager import BaseManager


class Sprite(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        dest = self.get_destination_path(self.name, ".png", path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        self.data.image.save(dest)

    def import_(self, *args):
        raise NotImplementedError("Import is not supported")
