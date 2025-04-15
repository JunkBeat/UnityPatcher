import logging

from utils import create_pptr, lock

from .BaseManager import BaseManager
from .Texture2D import Texture2D


class Font(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.name = data.name

    def export(self, path: str = None):
        self.read_typetree()
        rects = self.tree.get("m_CharacterRects")

        if not rects and not self.data.m_FontData:
            logging.warning(
                "%s Font object doesn't contain exportable data.", self.name
            )
            return

        new_path = path or self._get_base_dest(self.type_name, self.name)

        # export dump
        self.export_dump(new_path)

        # export atlas
        if rects:
            reader = self.data.reader
            file_id, path_id = self._extract_ids(self.tree["m_Texture"])
            data = create_pptr(reader, file_id, path_id).get_obj().read()
            Texture2D(data).export(new_path)

        # export vector font
        if self.data.m_FontData:
            ext = ".otf" if self.data.m_FontData[0:4] == b"OTTO" else ".ttf"
            dest = self.get_destination_path(self.name, ext, new_path)
            super().save(dest, self.data.m_FontData)

    def import_(self, font_path: str):
        self.data.set_font(font_path)
        with lock:
            self.data.save_via_tree()
