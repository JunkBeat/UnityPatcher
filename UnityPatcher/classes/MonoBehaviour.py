from typing import Union

from core.Settings import Settings
from helpers import TypeTreeManager, GeneralHelper

from .BaseManager import BaseManager


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
        dump - Path to json file or dict
        """
        if isinstance(dump, str):
            tree = GeneralHelper.read_json(tree)

        if self.data.serialized_type and self.data.serialized_type.nodes:
            self.data.reader.save_typetree(dump)
            return

        nodes = TypeTreeManager.get_typetree(
            self.data, self.script, Settings.game_folder, get_nodes=True
        )

        if nodes:
            self.data.reader.save_typetree(dump, nodes)
        else:
            raise Exception("Failed to get nodes")

    def export(self, path: str = None):
        full_name = self.name.replace("@", "-") + f" @{self.script.name}"
        self.tree = self.read_typetree()

        if not self.tree:
            raise Exception("Failed to read typetree")

        dest = self.get_destination_path(full_name, ".json", path)
        super().save_dump(dest, self.tree)

    def import_(self, dump_path: str):
        tree = GeneralHelper.read_json(dump_path)
        self.import_dump(tree)
