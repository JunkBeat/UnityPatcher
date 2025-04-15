from UnityPy.files import ObjectReader

from .BaseManager import BaseManager


class DefaultManager(BaseManager):
    def __init__(self, data):
        super().__init__(data)

        if isinstance(data, ObjectReader):
            tree = self.read_typetree()
            self.name = tree.get("m_Name")
        else:
            self.name = self.read_dump_value("m_Name")

    def export(self, path: str = None):
        super().export_dump(path)

    def import_(self, dump_path: str):
        super().import_dump(dump_path)
