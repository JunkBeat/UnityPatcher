import logging
import os
from typing import Union

from UnityPy.enums import ClassIDType
from UnityPy.streams import EndianBinaryReader

from core.Settings import Settings


RESOURCE_KEY_MAP = {"AudioClip": "m_Resource", "VideoClip": "m_ExternalResources"}


class ResourcePacker:
    def __init__(self, obj: Union["AudioClip", "VideoClip"], append_mode: bool = False):
        """
        Упаковывает ресурс (аудио или видео) в объект Unity.

        Аргументы:
            obj: Объект AudioClip или VideoClip, который нужно обработать
            append_mode: Если True, данные добавляются в конец, иначе заменяются
        """
        self.obj = obj
        self.append_mode = append_mode
        self.typetree = obj.read_typetree()
        self.asset = obj.assets_file
        self.asset_name = self.asset.name
        self.env = self.asset.environment
        self.is_bundle_parent = self.asset_name.startswith("CAB")
        self.resource_key = RESOURCE_KEY_MAP.get(obj.type.name)

    def get_or_create_resource(self):
        custom_res = Settings.custom_res
        resource_name = (
            #self.asset_name.replace(".sharedAssets", ".resource") if self.is_bundle_parent else
            os.path.basename(self.typetree[self.resource_key]["m_Source"]) if self.is_bundle_parent else
            f"{custom_res}.resource" if custom_res else
            self.typetree[self.resource_key]["m_Source"]
        )
        resource_data = self.find_file(resource_name)[1]

        if not resource_data:
            if self.is_bundle_parent:
                raise Exception(f"{resource_name} wasn't found in the loaded files")

            # SerializedFile
            resource_path = os.path.join(
                os.path.dirname(
                    self.find_file(self.asset_name)[0] or self.find_file("data.unity3d")[0]
                ), resource_name
            )
            # Если ресурс с целевым именем существует, но до сих пор не был загружен,
            # значит он не указан в аудиоклипах, соответственно мы можем его только
            # создать с нуля, т.к. не знаем, какие там были смещения
            if custom_res or os.path.exists(resource_path):
                resource_data = EndianBinaryReader(b"")
                self.env.files[resource_path] = resource_data
                self.append_mode = True
            else:
                raise Exception(f"{resource_name} wasn't found in the loaded files")

        if self.typetree[self.resource_key]["m_Source"] != resource_name:
            self.append_mode = True

        return resource_name, resource_data

    def pack(self):
        if self.obj.type not in [ClassIDType.AudioClip, ClassIDType.VideoClip]:
            raise Exception("Incorrect object type. Expected AudioClip or VideoClip")

        # mainData file
        if "m_AudioData" in self.typetree:
            self.typetree["m_Format"] = self.obj.m_Format
            self.typetree["m_AudioData"] = self.obj.m_AudioData
            self.obj.reader.save_typetree(self.typetree)
            return

        resource_name, resource_data = self.get_or_create_resource()

        file_data = (
            resource_data.bytes.tobytes()
            if isinstance(resource_data.bytes, memoryview)
            else resource_data.bytes
        )
        new_data = (
            self.obj.m_AudioData
            if self.obj.type == ClassIDType.AudioClip
            else self.obj.m_VideoData
        )

        if self.append_mode:
            # Добавление данных в конец
            data_offset = len(file_data)
            file_data += new_data
        else:
            # Подмена аудио/видео на оригинальной позиции
            source_path, data_offset, original_size = self.typetree[
                self.resource_key
            ].values()
            file_data = (
                file_data[:data_offset]
                + new_data
                + file_data[data_offset + original_size :]
            )
            size_diff = len(new_data) - original_size
            self.update_offsets(source_path, data_offset, size_diff)

        new_resource = EndianBinaryReader(file_data, resource_data.endian)
        self.update_resource(resource_name, new_resource)
        self.update_typetree(source=resource_name, offset=data_offset, size=len(new_data))

    def update_typetree(self, source: str = None, offset: int = None, size: int = None):
        if self.obj.type == ClassIDType.AudioClip:
            self.typetree["m_CompressionFormat"] = self.obj.m_CompressionFormat

        if self.obj.type == ClassIDType.VideoClip:
            self.typetree.update(
                {
                    "m_Format": self.obj.m_Format,
                    "Width": self.obj.Width,
                    "Height": self.obj.Height,
                    "m_ProxyWidth": self.obj.m_ProxyWidth,
                    "m_ProxyHeight": self.obj.m_ProxyHeight,
                }
            )

        updates = {
            k: v
            for k, v in {"m_Source": source, "m_Offset": offset, "m_Size": size}.items()
            if v is not None
        }

        self.typetree[self.resource_key].update(updates)
        self.obj.reader.save_typetree(self.typetree)

    def update_offsets(self, source: str, offset: int, size_diff: int):
        """
        Правка смещений для ассетов, идущих после целевого, в .resource

        Аргументы:
            offset: с какого смещения править
            source_path: что должно быть написано в поле источник
            size_diff: разница в байтах между старым и новым размером данных
        """
        for obj in self.asset.objects.values():
            if obj.type.name in ["AudioClip", "VideoClip"]:
                resource_key = RESOURCE_KEY_MAP[obj.type.name]
                typetree = obj.read_typetree()
                if (
                    typetree[resource_key]["m_Offset"] > offset
                    and typetree[resource_key]["m_Source"] == source
                ):
                    typetree[resource_key]["m_Offset"] += size_diff
                    obj.save_typetree(typetree)

    def update_resource(self, res_name: str, new_res: EndianBinaryReader):
        file_path = self.find_file(res_name)[0]
        if file_path is None:
            logging.error("Resource file '%s' not found.", res_name)
            return

        if self.is_bundle_parent:
            res_file = self.asset.parent.files[file_path]
            res_file.view = new_res.view
            res_file.Length = new_res.Length
            self.asset.parent.mark_changed()
        else:
            self.env.files[file_path] = new_res
            self.env.files[file_path].is_changed = True

    def find_file(self, res_name: str) -> tuple[str, object]:
        # .resource in bundle
        if self.is_bundle_parent:
            return res_name, self.asset.parent.files[res_name]

        # separate .resource file
        for file_path, file_obj in self.env.files.items():
            if os.path.basename(file_path) == res_name:
                return file_path, file_obj

        return None, None
