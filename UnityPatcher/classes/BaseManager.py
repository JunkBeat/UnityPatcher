import base64
import json
import logging
import os
import re
import zlib
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union

from UnityPy.enums import ClassIDType
from UnityPy.files import ObjectReader

from core.Settings import Settings
from helpers import GeneralHelper


TYPE_TO_CONTENT_ATTR = {
    ClassIDType.Texture2D: "image_data",
    ClassIDType.Texture2DArray: "image_data",
    ClassIDType.AudioClip: "m_AudioData",
    ClassIDType.VideoClip: "m_VideoData",
}

BASE64_BYTES_PREFIX = "BYTES: "
BASE64_LIST_PREFIX = "LIST: "


def decode_base64(data: str, prefix: str) -> Union[bytes, list, str]:
    """Decodes a base64 string with the specified prefix, returning bytes or a list of ints."""
    encoded_data = data[len(prefix):]
    try:
        decompressed_data = zlib.decompress(base64.b64decode(encoded_data))
        return decompressed_data
    except Exception as e:
        logging.error(f"Error decoding {prefix}: {e}")
        return data


def decode_base64_in_tree(tree: Any) -> Any:
    if isinstance(tree, dict):
        return {k: decode_base64_in_tree(v) for k, v in tree.items()}
    if isinstance(tree, list):
        return [decode_base64_in_tree(v) for v in tree]
    if isinstance(tree, str):
        if tree.startswith(BASE64_BYTES_PREFIX):
            return decode_base64(tree, BASE64_BYTES_PREFIX)
        elif tree.startswith(BASE64_LIST_PREFIX):
            decoded_bytes = decode_base64(tree, BASE64_LIST_PREFIX)
            return list(decoded_bytes) if isinstance(decoded_bytes, bytes) else decoded_bytes

    return tree


def preprocess_tree(tree: dict):
    # после чтения typetree некоторые значения имеют тип списка чисел
    # преобразуем их в байты для последующей сериализации (если чисел много)
    def serialize_list_to_bytes(lst: list) -> str:
        if all(isinstance(i, int) and 0 <= i <= 255 for i in lst) and len(lst) > 150:
            return bytes(lst)
        return lst # Вернётся, если список не подходит под условия

    # сжимает данные и кодирует в base64. В UABEA это список UInt8 (он занимает больше места)
    # добавляем уникальный префикс, чтобы в дальнейшем декодировать правильные поля
    def compress_data(data: Union[memoryview, bytes]):
        compressed_data = zlib.compress(data.tobytes() if isinstance(data, memoryview) else data)
        return base64.b64encode(compressed_data).decode("utf-8")

    for key, value in tree.items():
        if isinstance(value, list) and value:
            serialized = serialize_list_to_bytes(value)
            if isinstance(serialized, bytes):
                tree[key] = BASE64_LIST_PREFIX + compress_data(serialized)
            else:
                continue
        elif isinstance(value, (memoryview, bytes)):
            tree[key] = BASE64_BYTES_PREFIX + compress_data(value)
        elif isinstance(value, dict) and value:
            tree[key] = preprocess_tree(value)

    return tree


class BaseManager(ABC):
    def __init__(self, data):
        self._name: str = None
        self.tree: dict = None
        self.data = data
        self.type = data.type
        self.type_name = data.type.name
        self.path_id = data.path_id

    @abstractmethod
    def export(self, path: str = None):
        raise NotImplementedError("This method should be overridden")

    @abstractmethod
    def import_(self, file_path: Union[str, List[str]]):
        raise NotImplementedError("This method should be overridden")

    @staticmethod
    def _extract_ids(data: dict) -> tuple:
        file_id = data.get("m_FileID")
        path_id = data.get("m_PathID")
        return file_id, path_id

    @staticmethod
    def save(dest: str, content: Union[bytes, memoryview]):
        if not dest or not isinstance(dest, str):
            raise ValueError("Invalid destination path.")

        if not isinstance(content, (bytes, memoryview)):
            raise ValueError(f"Invalid content type: {type(content).__name__}")

        try:
            directory = os.path.dirname(dest)
            os.makedirs(directory, exist_ok=True)
            if not os.access(directory, os.W_OK):
                raise PermissionError(f"No write access to the directory: {directory}")

            with open(dest, "wb") as f:
                f.write(content)
        except Exception as e:
            raise RuntimeError(f"Unexpected error while saving file: {e}")

    def save_dump(self, dest: str, tree: dict):
        if not isinstance(tree, dict):
            raise TypeError(
                f"Expected dictionary for 'tree', got {type(tree).__name__}"
            )

        tree = preprocess_tree(tree)
        content = json.dumps(tree, indent=2, ensure_ascii=False).encode("utf-8")
        self.save(dest, content)

    def import_dump(self, tree: Union[str, dict]):
        """
        tree - Path to json file or dict
        """
        if isinstance(tree, str):
            tree = GeneralHelper.read_json(tree)

        tree = decode_base64_in_tree(tree)

        if not isinstance(tree, dict):
            raise TypeError(f"Tree must be a dictionary, not {type(tree).__name__}")

        if isinstance(self.data, ObjectReader):
            self.data.save_typetree(tree)
        else:
            self.data.reader.save_typetree(tree)

    def export_dump(self, path: str = None):
        tree = self.read_typetree()

        if not tree:
            raise Exception("Failed to read non MonoBehaviour typetree")

        name = self.name or tree.get("m_Name")
        dest = self.get_destination_path(name, path=path, is_dump=True)
        self.save_dump(dest, tree)

    def export_raw(self, path: str = None):
        dest = self.get_destination_path(self.name, path=path, is_raw=True)
        self.save(dest, self.raw_data)
        self.export_raw_content(path)

    def export_raw_content(self, path: str = None):
        attr = TYPE_TO_CONTENT_ATTR.get(self.type)
        if attr:
            if self.type == ClassIDType.Texture2D and not self.data.m_CompleteImageSize:
                return
            content = getattr(self.data, attr, None)
            if content:
                dest = self.get_destination_path(
                    self.name, path=path, extension=".content"
                )
                self.save(dest, content)

    def import_raw_content(self, file: str):
        if not os.path.exists(file):
            raise ValueError(f"Invalid file: {file}")

        attr = TYPE_TO_CONTENT_ATTR.get(self.type)
        if attr:
            content = GeneralHelper.read_binary_file(file)
            setattr(self.data, attr, content)
            self.save_data()

    def get_destination_path(
        self,
        name: str,
        extension: str = "",
        path: str = None,
        is_dump: bool = False,
        is_raw: bool = False,
    ) -> str:
        pathid = str(self.path_id)
        fixed_name = self._get_fixed_name(name)
        source_name = self.get_source_name()
        base_dest = path or self._get_base_dest()
        extension = ".dump.json" if is_dump else ".obj" if is_raw else extension

        return os.path.join(
            base_dest, f"{fixed_name} [{source_name}] #{pathid}{extension}"
        )

    def _get_base_dest(
        self,
        type_name: str = None,
        group_name: str = None,
    ) -> str:
        path_parts = [Settings.output_folder]

        for part in Settings.group_option.split("_"):
            if part == "type":
                path_parts.append(type_name or self.type_name)

            elif part == "source":
                path_parts.append(self.get_source_name())

        if group_name:
            path_parts.append(group_name)

        return os.path.join(*path_parts)

    def get_source_name(self) -> str:
        return self.data.assets_file.name

    def get_full_source_name(self) -> str:
        source = self.get_source_name()
        if source.startswith("CAB"):
            bundle_name = self.data.assets_file.parent.name
            source = os.path.join(bundle_name, source)
        return source

    def read_typetree(self):
        if not self.tree:
            self.tree = self.data.read_typetree()
        return self.tree

    def read_dump_value(self, value: str) -> str:
        typetree = self.data.reader.read_trimed_typetree(value)
        return typetree.get(value)

    def get_script_name(self) -> Optional[str]:
        return getattr(getattr(self, "script", None), "name", None)

    @property
    def name(self) -> str:
        return self._name or f"Unnamed {self.type_name}"

    @name.setter
    def name(self, value: str):
        self._name = self._get_fixed_name(value)

    def _get_fixed_name(self, value: str) -> str:
        return self._fix_name(value) if value else f"Unnamed {self.type_name}"

    @staticmethod
    def _fix_name(name: str) -> str:
        fixed_name = re.sub(r'[#<>:"/\\|?*\[\]]', "-", name)

        search_string = "(Clone)"
        count = fixed_name.count(search_string)

        if count > 1:
            fixed_name = fixed_name.replace(search_string * count, f"{search_string}x{count}")
        
        return fixed_name

    @property
    def raw_data(self):
        return self.data.get_raw_data()

    @raw_data.setter
    def raw_data(self, content: bytes):
        self.data.set_raw_data(content)

    def __str__(self):
        script_name = self.get_script_name()
        source = self.get_full_source_name()

        return (
            f"Name: {self.name}\n"
            f"Type: {self.type_name}\n"
            f"Script: {script_name}\n"
            f"PathID: {self.path_id}\n"
            f"Source: {source}"
        )
