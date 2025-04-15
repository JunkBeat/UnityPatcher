from utils import create_pptr

from .DefaultManager import DefaultManager
from .MonoBehaviour import MonoBehaviour
from .Texture2D import Texture2D


class SDF(MonoBehaviour):
    def __init__(self, data):
        super().__init__(data)

    def export(self, path: str = None) -> None:
        reader = self.data.reader
        new_path = path or self._get_base_dest("SDF", self.name)

        # Export MonoBehaviour
        super().export(new_path)

        # Export Material
        # ~ Unity 2020 uses m_Material instead of material
        file_id, path_id = self._extract_ids(self.tree.get("material") or self.tree["m_Material"])
        data = create_pptr(reader, file_id, path_id).get_obj()
        DefaultManager(data).export(new_path)

        # Export Atlas
        # the atlas key is actually used in earlier Unity versions, now it contains zeros
        for atlas in self.tree.get("m_AtlasTextures") or [self.tree["atlas"]]:
            file_id, path_id = self._extract_ids(atlas)
            data = create_pptr(reader, file_id, path_id).get_obj().read()
            Texture2D(data).export(new_path)

    def export_dump(self, path: str = None):
        super().export(path)

    def export_raw(self, path: str = None):
        super().export_raw(path)

    def import_(self, *args):
        raise Exception(
            "SDF class doesn't support import. Import atlas "
            "and dump separately through the corresponding classes."
        )
