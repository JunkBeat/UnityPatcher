import json
import logging
import os
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple, Union

from PIL import Image


@dataclass
class UndetectedAsset:
    name: str
    source_file: str
    path_id: int
    patch_files: List["PatchFile"]


def read_file_content(file, path: str) -> Union[str, dict, Image.Image, bytes]:
    if path.endswith(".json"):
        return json.load(file)

    if path.endswith(".txt"):
        return file.read().decode("utf-8")

    if path.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
        return Image.open(file)

    return file.read()


class PatchFileType(IntEnum):
    Regular = 0
    Dump = 1
    Raw = 2
    RawContent = 3


class PatchFile:
    def __init__(self, path: str):
        self.path = path
        self.object_name = None
        self.source_file = None
        self.script_name = None
        self.path_id = None
        self.index = None
        self.extension = None
        self.file_type = None
        self.detected = False # asset was found in loaded assets
        self.imported = False
        self.parse_filename()

    def parse_filename(self):
        """
        Possible names:
        OBJECT_NAME [SOURCE_FILE] #PATHID.EXTENSION

        MonoBehaviour:
        OBJECT_NAME @SCRIPT_NAME [SOURCE_FILE] #PATHID.EXTENSION

        Texture2DArray:
        ...#PATHID_INDEX.EXTENSION

        Dumps may have a clarifying double extension:
        .dump.json

        Raw data have .bin extension
        """
        pattern = re.compile(
            r"^(?P<object_name>[^#@\[\]]+)"  # OBJECT_NAME
            r"(?: @(?P<script_name>[^\[\]]+))?"  # @SCRIPT_NAME (optional)
            r" \[(?P<source_file>[^\]]+)\]"  # [SOURCE_FILE]
            # #PATHID (which can be positive or negative) or #PATHID_INDEX.EXTENSION
            r" #(?P<path_id>-?\d+)(?:_(?P<index>\d+))?\.(?P<extension>\w+(\.\w+)?)$"
        )
        match = pattern.match(self.path)
        if match:
            self.object_name = os.path.basename(match.group("object_name"))
            self.source_file = match.group("source_file")
            self.script_name = match.group("script_name")
            self.path_id = match.group("path_id")
            self.index = match.group("index")
            full_extension = match.group("extension")

            if self.path_id is not None:
                self.path_id = int(self.path_id)

            if self.index is not None:
                self.index = int(self.index)

            self.extension = full_extension

            file_types = {
                "dump.json": PatchFileType.Dump,
                "obj": PatchFileType.Raw,
                "content": PatchFileType.RawContent,
            }

            self.file_type = file_types.get(full_extension, PatchFileType.Regular)

    def read_file(self) -> Union[str, dict, Image.Image, bytes]:
        """
        Reads a patch file. Supports text, JSON, images (PIL), and binary files.
        """
        with open(self.path, "rb") as file:
            return read_file_content(file, self.path)

    def mark_imported(self):
        self.imported = True

    def mark_detected(self):
        self.detected = True

    @property
    def is_dump(self) -> bool:
        return self.file_type == PatchFileType.Dump

    @property
    def is_raw(self) -> bool:
        return self.file_type == PatchFileType.Raw

    @property
    def is_raw_content(self) -> bool:
        return self.file_type == PatchFileType.RawContent

    @property
    def is_regular(self) -> bool:
        return self.file_type == PatchFileType.Regular


class PatchData:
    def __init__(self, source: Union[str, List["PatchFile"]]):
        self.patch_folder = None

        if isinstance(source, str):
            self.patches = self.process_data(source)
            self.patch_folder = source
        elif (
            isinstance(source, list)
            and all(isinstance(item, PatchFile) for item in source)
        ):
            self.patches = source
        else:
            raise ValueError("Expected path to patch folder or list of PatchFile")

    @property
    def undetected_assets(self) -> List[UndetectedAsset]:
        undetected_assets_dict: Dict[Tuple[str, int], UndetectedAsset] = {}

        for patch in self.patches:
            if not patch.detected:
                key = (patch.source_file, patch.path_id)
                if key not in undetected_assets_dict:
                    undetected_assets_dict[key] = UndetectedAsset(
                        name=patch.object_name,
                        source_file=patch.source_file,
                        path_id=patch.path_id,
                        patch_files=[],
                    )
                undetected_assets_dict[key].patch_files.append(patch)

        return list(undetected_assets_dict.values())

    @property
    def source_names(self) -> List[str]:
        return [patch.source_file for patch in self.patches]

    @property
    def paths(self) -> List[str]:
        return [patch.path for patch in self.patches]

    @property
    def imported_patches(self) -> "PatchData":
        return PatchData([patch for patch in self.patches if patch.imported])

    def remove_by_path(self, target_path: str):
        self.patches = [pf for pf in self.patches if pf.path != target_path]

    def mark_imported(self):
        for patch in self.patches:
            patch.mark_imported()
    
    def mark_detected(self):
        for patch in self.patches:
            patch.mark_detected()

    def display_info(self):
        logging.info("\n[Patch Files]")
        for patch_file in self.patches:
            logging.info("Path: %s", patch_file.path)
            logging.info("Object Name: %s", patch_file.object_name)
            logging.info("Source File: %s", patch_file.source_file)
            logging.info("Script Name: %s", patch_file.script_name)
            logging.info("Path ID: %s", patch_file.path_id)
            logging.info("Index: %s", patch_file.index)
            logging.info("Extension: %s", patch_file.extension)
            logging.info("Is Dump: %s", patch_file.is_dump)
            logging.info("Is Raw: %s", patch_file.is_raw)
            logging.info("Is Raw Content: %s", patch_file.is_raw_content)
            logging.info("")

    @classmethod
    def process_data(cls, path: str) -> List["PatchFile"]:
        """
        path: str - path to patch files folder
        """
        patch_files = []
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                patch_files.extend(
                    PatchFile(os.path.join(root, file)) for file in files
                )
        else:
            raise ValueError("Invalid path")

        return [
            pf
            for pf in patch_files
            if pf.path_id and (pf.source_file or pf.object_name or pf.script_name)
        ]

    def get_patch(
        self,
        source_file: str,
        path_id: int,
        script_name: str = None,
        object_name: str = None,
    ) -> Optional["PatchData"]:
        patches = [
            patch
            for patch in self.patches
            if patch.source_file == source_file
            and patch.path_id == path_id
            and (script_name is None or patch.script_name == script_name)
            and (object_name is None or patch.object_name == object_name)
        ]

        if patches:
            patches.sort(key=lambda x: (x.index is not None, x.index))
            return PatchData(patches)

        return None

    def read(self) -> List[bytes]:
        return [patch.read_file() for patch in self.patches if patch.read_file() is not None]

    def sort_by_source(self) -> Dict[str, List[int]]:
        sorted_patches = {}
        for patch in self.patches:
            sorted_patches.setdefault(patch.source_file, []).append(patch.path_id)
        return sorted_patches

    def sort_by_file_type(self) -> "PatchData":
        """
        Сортирует файлы PatchFile
        """
        self.patches.sort(key=self._sorting_priority)
        return self.patches

    @staticmethod
    def _sorting_priority(file: "PatchFile") -> int:
        """
        Определяет приоритет сортировки:
        - is_raw=True: приоритет 0
        - is_dump=True: приоритет 1
        - is_raw_content=True: приоритет 2
        - Остальные файлы (regular): приоритет 3
        """
        if file.is_raw:
            return 0
        if file.is_dump:
            return 1
        if file.is_raw_content:
            return 2
        return 3
