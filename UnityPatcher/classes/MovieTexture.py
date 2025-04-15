import os

from .AudioClip import AudioClip
from .BaseManager import BaseManager


class MovieTexture(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.m_Name

    def export(self, path: str = None):
        new_path = path or self._get_base_dest(self.type_name, self.name)

        # Export AudioClip
        audioclip_data = self.data.m_AudioClip.get_obj().read()
        AudioClip(audioclip_data).export(new_path)

        # Export MovieTexture
        dest = self.get_destination_path(self.name, ".bin", new_path)
        super().save(dest, self.data.m_MovieData)

    def import_(self, movie_file: str):
        if not os.path.isfile(movie_file):
            raise FileNotFoundError(f"File not found: {movie_file}")

        with open(movie_file, "rb") as f:
            self.data.m_MovieData = f.read()
