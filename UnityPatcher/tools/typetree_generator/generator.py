"""
Container for TypeTreeGenerator class and export methods.

author: jrobinson3k1
source: https://github.com/jrobinson3k1/typetree_unity
"""

import os
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from AssetStudio import (
    AssemblyLoader,
    SerializedTypeHelper,
    TypeDefinitionConverter,
    TypeTreeNode,
)
from Mono.Cecil import AssemblyDefinition
from System import Array
from System.Collections.Generic import List

from .logger import get_logger

_SEM_VER_REGEX = r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
_PPTR_REGEX = r"^PPtr<(.+)>$"
_BLACKLIST_CLASSES = [
    "GameObject",
    "MonoBehaviour",
    "MonoScript",
    "Sprite",  # Unity classes
    "HxOctreeNode`1",
    "HxOctreeNode`1/NodeObject",
    "Object",
]
"""Unity-specific classes and known classes that can cause stackoverflow or can't be parsed"""

logger = get_logger()


def create_generator(*args):
    """Create a TypeTreeGenerator."""
    return TypeTreeGenerator(*args)


def _normalize_unity_version(version):
    """
    Normalize a version string to a true Semantic Versioning string.

    Unity follows Semantic Versioning (Major.Minor.Patch). However, build versions
    tend to have a qualifier after the Patch value. Strip that out.
    """
    match = re.search(_SEM_VER_REGEX, version)
    if not match:
        raise ValueError(f"Invalid Unity build version: {version}")

    normalized_version = match.group(0)
    if normalized_version != version:
        logger.info("Resolved Unity version from %s to %s", version, normalized_version)
    return normalized_version


class _AssemblyFile:
    def __init__(self, base_name):
        self.base_name = base_name
        self.file_name = base_name + ".dll"


@dataclass(frozen=True)
class _ClassRef:
    assembly: _AssemblyFile
    class_name: str


class TypeTreeGenerator:
    """
    Generates and exports type trees from Unity assemblies.

    Methods
    -------
    generate_tree(assembly_file, class_names=None) : Dict[str]
    get_cached_trees() : Dict[str]
    clear_cache()
    """

    _loader: AssemblyLoader
    _tree_cache = {}

    def __init__(self, assembly_folder, unity_version, libraries):
        """
        Generate and export type trees from Unity assemblies.

        Parameters
        ----------
        assembly_folder : str
            Path to Unity assemblies
        unity_version : str
            Unity build version (Format: "Major.Minor.Patch")
        libraries : list
            List of libraries to process
        """
        unity_version = _normalize_unity_version(unity_version)
        self._unity_version = Array[int]([int(s) for s in unity_version.split(".")])
        self._available_classes = self._find_all_classes(assembly_folder, libraries)
        self._loader = self._create_loader(assembly_folder)
        logger.debug(
            "Init TypeTreeGenerator: %d classes found", len(self._available_classes)
        )

    def generate_type_trees(self, class_names=None):
        """
        Generate type trees for the specified classes (all if not specified).

        Referenced class types will be automatically dumped. Results are cached.

        Parameters
        ----------
        assembly_file : str
            File name of the assembly to dump (typically Assembly-CSharp.dll)
        class_names : Union[str, Iterable<str>], optional
            The classes to dump (all if None)

        Returns
        -------
        dict[str, list]
            Dictionary of class names containing a list of type definitions
        """
        if class_names:
            if isinstance(class_names, str):
                class_names = [class_names]
            if not isinstance(class_names, Iterable):
                raise TypeError(
                    f"expected str or Iterable<str>, got {type(class_names)}"
                )
            class_refs = [
                x for x in self._available_classes if x.class_name in class_names
            ]
        else:
            class_refs = list(self._available_classes)

        if not class_refs:
            logger.debug("No available classes")
            return None

        logger.debug("Generating trees for %s classes", len(class_refs))

        trees = self._generate_type_trees(class_refs)

        # cache results
        count = 0
        for key, value in trees.items():
            count += len(value)
            if key not in self._tree_cache:
                self._tree_cache[key] = value.copy()
            else:
                self._tree_cache[key].update(value.copy())

        logger.debug("Generated trees for %s classes", count)

        return self._flatten_tree(trees)

    def _generate_type_trees(self, class_refs):
        trees = {}
        local_blacklist = _BLACKLIST_CLASSES.copy()
        class_deque = deque(class_refs)
        while class_deque:
            class_ref = class_deque.popleft()
            if class_ref.class_name in local_blacklist:
                logger.debug("Skipping blacklisted class: %s", class_ref.class_name)
                continue

            # TODO: Check cache, add parameter to allow checking from cache
            type_tree, referenced_classes = self._dump_class(
                class_ref.assembly.file_name, class_ref.class_name
            )

            if type_tree:
                if class_ref.assembly.base_name not in trees:
                    trees[class_ref.assembly.base_name] = type_tree
                else:
                    trees[class_ref.assembly.base_name].update(type_tree)
            else:
                local_blacklist.append(class_ref.class_name)

            for class_name in referenced_classes:
                if class_name in local_blacklist:
                    continue

                referenced_class_ref = None
                for ref in self._available_classes:
                    if ref.class_name == class_name:
                        referenced_class_ref = ref
                        break

                if not referenced_class_ref:
                    local_blacklist.append(class_name)
                    logger.warning("Failed to find referenced class %s", class_name)
                    continue

                if class_deque.count(referenced_class_ref) == 0 and (
                    referenced_class_ref.assembly.base_name not in trees
                    or referenced_class_ref.class_name
                    not in trees[referenced_class_ref.assembly.base_name]
                ):
                    class_deque.append(referenced_class_ref)
                    logger.debug(
                        "Appended referenced class %s to queue",
                        referenced_class_ref.class_name,
                    )

        return trees

    def _dump_class(self, assembly_name, class_name):
        type_def = self._loader.GetTypeDefinition(assembly_name, class_name)
        if not type_def:
            logger.warning("Could not find class %s in %s", class_name, assembly_name)
            return None, []

        nodes, referenced_classes = self._convert_to_type_tree_nodes(type_def)
        return {type_def.FullName: nodes}, referenced_classes

    def _convert_to_type_tree_nodes(self, type_def):
        logger.debug("Generating type tree nodes for %s", type_def.FullName)

        nodes = List[TypeTreeNode]()
        type_helper = SerializedTypeHelper(self._unity_version)
        type_helper.AddMonoBehaviour(nodes, 0)
        try:
            type_def_converter = TypeDefinitionConverter(type_def, type_helper, 1)
            nodes.AddRange(type_def_converter.ConvertToTypeTreeNodes())
        except Exception:
            logger.exception("Failed getting class: %s", type_def.FullName)
            return None, []

        type_tree_nodes = []
        referenced_classes = []
        for node in nodes:
            type_tree_nodes.append(
                {
                    "level": node.m_Level,
                    "type": node.m_Type,
                    "name": node.m_Name,
                    "meta_flag": node.m_MetaFlag,
                }
            )

            # check for referenced classes
            if (
                (match := re.match(_PPTR_REGEX, node.m_Type))
                and (pptr_class := match.group(1))
                and pptr_class not in referenced_classes
            ):
                referenced_classes.append(pptr_class)

        return type_tree_nodes, referenced_classes

    def _find_class_location(self, class_name):
        for assembly_base, class_list in self._available_classes:
            if class_name in class_list:
                return assembly_base

        return None

    @classmethod
    def _flatten_tree(cls, tree):
        flat_tree = {}
        for _, value in tree.items():
            flat_tree.update(value)
        return flat_tree

    @classmethod
    def _find_all_classes(cls, assembly_folder, libraries: List[str]):
        """Find fully qualified class names from a game's assemblies."""
        class_refs = set()
        for library in libraries:
            file_path = os.path.join(assembly_folder, library + ".dll")
            if not os.path.isfile(file_path):
                raise ValueError(f"{library}.dll not found in {assembly_folder}")

            assembly_def = AssemblyDefinition.ReadAssembly(file_path)
            for type_def in assembly_def.MainModule.GetTypes():
                class_refs.add(_ClassRef(_AssemblyFile(library), type_def.FullName))

        return class_refs

    def get_cached_trees(self):
        """
        Get a copy of the type trees that have been created from the generate_tree method.

        Returns
        -------
        dict[str, dict[str, list]]
            Dictionary of assembly file names containing dictionary of the type tree for class names
        """
        return self._tree_cache.copy()

    def clear_cache(self):
        """Clear type tree cache populated from the generate_tree method."""
        self._tree_cache.clear()

    @classmethod
    def _create_loader(cls, assembly_folder):
        loader = AssemblyLoader()
        loader.Load(assembly_folder)
        return loader
