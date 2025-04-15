import json
import os
from typing import List
from UnityPy.enums import BuildTarget as BT

from enums import PLATFORM_MAPPING, PlatformCategory
from utils import ask_directory


def is_correct_platform(platform: BT, selected_platforms: List[PlatformCategory]):
    return any(platform in PLATFORM_MAPPING[plat] for plat in selected_platforms)


def read_binary_file(file: str, length: int = None) -> bytes:
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")

    with open(file, "rb") as f:
        content = f.read(length)

    return content


def read_json(file: str):
    if not file.endswith(".json"):
        raise ValueError(
            f"Invalid file. Expected .json, got {os.path.splitext(file)[1]}: {file}"
        )

    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def find_game_folder():
    current_dir = os.getcwd()
    data_folder = None

    for folder in os.listdir(current_dir):
        if folder.endswith("_Data") and os.path.isdir(folder):
            data_folder = folder
            break

    if not data_folder:
        data_folder = ask_directory("Select the game's Data folder")

    return data_folder
