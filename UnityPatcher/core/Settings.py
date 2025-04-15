from enum import Enum
from typing import List

from enums import TextureCompressionQuality as TexQuality


class Settings:
    """
    Variables for temporary data storage
    (do not edit)
    """

    game_folder: str = ""
    output_folder: str = ""
    asset_types: List[str] = []
    custom_res: str = ""
    """
    Variables for storing actual settings
    (you can edit them)
    """
    # General
    blacklist: List[str] = []
    python_typetree_reader: bool = False
    debug_mode: bool = False
    temp_path: str = "_TEMP"
    fallback_version: str = "2.5.0f5"
    cn_key: str = ""

    # Packing
    ignore_object_name: bool = False
    transcode_video: bool = False
    transcode_quality: str = "medium"
    texture_compression_quality: TexQuality = TexQuality.BEST
    generate_mipmaps: bool = False
    dont_compress_texture: bool = False
    dont_compress_audio: bool = False
    resource_append_mode: bool = False
    recreate_output_dir: bool = False
    backup_before_saving: bool = False

    # Unpacking
    group_option: str = "type"

    @classmethod
    def update_setting(cls, key, value):
        if hasattr(cls, key):
            current_value = getattr(cls, key)

            if isinstance(current_value, Enum):
                enum_type = type(current_value)
                if isinstance(value, str):
                    try:
                        value = enum_type(value)
                    except ValueError:
                        raise ValueError(
                            f"Invalid value '{value}' for setting '{key}'. Expected one of: {[e.value for e in enum_type]}"
                        )

            if isinstance(value, type(current_value)) or value is None:
                setattr(cls, key, value)
            else:
                raise ValueError(
                    f"Expected {type(current_value).__name__} for {key}, but got {type(value).__name__}"
                )

    @classmethod
    def load_from_args(cls, args=None):
        if args:
            args_dict = vars(args)
            for key, value in args_dict.items():
                cls.update_setting(key, value)

    @classmethod
    def display_settings(cls):
        settings = {k: v for k, v in cls.__dict__.items() if not k.startswith("_")}
        for key, value in settings.items():
            print(f"{key}: {value}")
