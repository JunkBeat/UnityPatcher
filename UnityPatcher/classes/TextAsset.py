import json
import os

from .BaseManager import BaseManager


class TextAsset(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        content = bytes(self.data.script)

        try:
            decoded_content = content.decode("utf-8-sig")
            try:
                _ = json.loads(decoded_content)
                ext = ".json"
            except json.decoder.JSONDecodeError:
                ext = ".txt"
        except Exception:
            ext = ".bin"

        dest = self.get_destination_path(self.name, ext, path)
        super().save(dest, content)

    def import_(self, text_file: str):
        if not os.path.isfile(text_file):
            raise FileNotFoundError(f"File not found: {text_file}")

        ext = os.path.splitext(text_file)[1]

        if ext in [".json", ".txt", ".bin"]:
            with open(text_file, "rb") as f:
                self.data.script = f.read()
                self.data.save()
        else:
            raise ValueError(f"Invalid file. Expected json/txt/bin, got {text_file}")
