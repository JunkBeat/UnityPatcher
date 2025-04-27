from typing import Union

from core.Settings import Settings
from helpers import TypeTreeManager, GeneralHelper

from .BaseManager import BaseManager
from .BaseManager import decode_base64_in_tree


class MonoBehaviour(BaseManager):
    def __init__(self, data):
        super().__init__(data)
        self.script = self.data.m_Script.get_obj().read()
        self.name = data.name or self._get_gameobject_name()

    def _get_gameobject_name(self):
        try:
            name = self.data.m_GameObject.get_obj().read().name
            return " ".join(name.split())
        except Exception:
            return None

    def read_typetree(self) -> dict:
        """
        Overridden method for reading a typetree.
        If the data is serialized and there are nodes, returns the typetree.
        Otherwise, uses generation via TypeTreeManager.
        """
        if self.data.serialized_type and self.data.serialized_type.nodes:
            return self.data.read_typetree()

        return TypeTreeManager.get_typetree(
            self.data,
            self.script,
            Settings.game_folder,
        )

    def import_dump(self, dump: Union[str, dict]):
        """
        Overridden method for importing a typetree dump.

        Args:
            dump (Union[str, dict]): Path to JSON file or dictionary.
        """
        if isinstance(dump, str):
            dump = GeneralHelper.read_json(dump)
        
        if not isinstance(dump, dict):
            raise TypeError(f"Unsupported dump type: {type(dump).__name__}")
        
        tree = decode_base64_in_tree(dump)
    
        if self.data.serialized_type and self.data.serialized_type.nodes:
            self.data.reader.save_typetree(tree)
            return

        nodes = TypeTreeManager.get_typetree(
            self.data, self.script, Settings.game_folder, get_nodes=True
        )

        if not nodes:
            raise RuntimeError("Failed to get nodes")

        self.data.reader.save_typetree(tree, nodes)

    def export(self, path: str = None):
        full_name = self.name.replace("@", "-") + f" @{self.script.name}"
        self.tree = self.read_typetree()

        if not self.tree:
            raise Exception("Failed to read typetree")

        dest = self.get_destination_path(full_name, ".json", path)
        super().save_dump(dest, self.tree)

    def import_(self, dump_path: str):
        self.import_dump(dump_path)
