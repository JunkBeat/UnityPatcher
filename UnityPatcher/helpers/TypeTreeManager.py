import logging
import os

from tools import generate_typetree
from utils import ask_directory


def setup_managed(managed_path: str):
    if not os.path.exists(managed_path):
        logging.warning("The provided Managed folder does not exist")
        managed_path = ask_directory("Select Managed folder")

    if managed_path:
        TypeTreeManager.assembly_folder = managed_path


def find_managed_folder(game_folder: str):
    for dirpath, dirnames, _ in os.walk(game_folder):
        if "Managed" in dirnames:
            return os.path.join(dirpath, "Managed")
    return None


class TypeTreeManager:
    typetree_cache: dict = {}
    assembly_folder: str = None

    @staticmethod
    def reset_cache():
        TypeTreeManager.typetree_cache = {}

    @staticmethod
    def get_typetree(obj, script, game_folder: str, get_nodes=False):
        """
        Gets the type tree for the object. If the type tree is not found in the cache, it is generated.

        obj: The object for which the type tree is required.
        script: Script containing the type information.
        game_folder: The folder with the game data.
        get_nodes: If True, returns the type nodes, otherwise the result of calling read_typetree.
        return: The type tree nodes, or None if the type tree could not be obtained.
        """
        assembly_name = script.m_AssemblyName
        namespace = script.m_Namespace
        class_name = script.m_ClassName

        class_path = f"{namespace}.{class_name}" if namespace else class_name
        nodes = TypeTreeManager.typetree_cache.get(assembly_name, {}).get(class_path)

        if not nodes:
            assembly_folder = TypeTreeManager.assembly_folder or find_managed_folder(
                game_folder
            )

            if not assembly_folder:
                logging.warning(
                    "[WARN] Typetree was not generated because Managed was not in the game folder."
                )
                return None

            data: dict = generate_typetree(
                assembly_folder=assembly_folder,
                unity_version=".".join(map(str, obj.version)),
                libraries=assembly_name.replace(".dll", ""),
                class_names=class_path,
                disable_output=True,
            )

            if data and class_path in data:
                TypeTreeManager.typetree_cache.setdefault(assembly_name, {}).update(
                    data
                )
                nodes = TypeTreeManager.typetree_cache.get(assembly_name, {}).get(
                    class_path
                )

        if nodes:
            return nodes if get_nodes else obj.read_typetree(nodes)

        logging.error("Nodes not found: <%s>", class_path)
        return None
