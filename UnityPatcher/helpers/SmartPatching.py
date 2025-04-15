import copy
import hashlib
import json
import logging
import os
from enum import Enum
from typing import Dict, List
from UnityPy.files import BundleFile, WebFile

from core.PatchFile import PatchData


class PatchType(Enum):
    Patch = "PATCH"


def calculate_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def save_hashes(hashes: dict) -> None:
    with open("hash_data.json", "w") as f:
        json.dump(hashes, f, indent=2)


def load_hashes() -> dict:
    file_path = "hash_data.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

# ==== Patch ==== #

def filter_patches(
    input_folder: str, output_folder: str, patch_data: PatchData
) -> PatchData:
    """
    Filters PatchData based on hashes. If at least one hash does not match, 
    the original patch_data is returned for a complete overwrite.
    """
    hashes = load_hashes()
    if not hashes:
        return patch_data

    root_key = PatchType.Patch.value
    new_hashes = copy.deepcopy(hashes)
    new_patch_data = copy.deepcopy(patch_data)

    for assets_file, value in hashes.get(root_key, {}).items():
        if not assets_file.startswith(output_folder):
            continue

        if not os.path.exists(assets_file):
            del new_hashes[root_key][assets_file]
            continue

        # Check assets file hash
        if calculate_hash(assets_file) != value["hash"]:
            new_hashes[root_key][assets_file]["patch_files"] = {}
            continue

        # Checking file hashes in the patch_files dictionary
        for patch_path, patch_hash in value.get("patch_files", {}).items():
            if not os.path.exists(patch_path):
                continue

            if calculate_hash(patch_path) == patch_hash:
                new_patch_data.remove_by_path(patch_path)
            # If at least one hash does not match, we return the original data
            elif input_folder != output_folder:
                return patch_data

    save_hashes(new_hashes)
    return new_patch_data


def update_hash_data(game_loader, imported_patches: PatchData):
    """
    Updates hash data for all modified files and their patches.
    """
    def get_root_folder(path: str) -> str:
        return os.path.normpath(path).split(os.sep)[0]

    def merge_patch_files(
        old_patches: Dict[str, str], new_patches: Dict[str, str]
    ) -> Dict[str, str]:
        merged = old_patches.copy()
        merged.update(new_patches)
        return merged

    def process_env_file(filename: str, file, hash_data: dict):
        if not hasattr(file, "objects"):
            return

        archive_path = os.path.relpath(filename, game_loader.game_folder)
        modified_file = os.path.join(get_root_folder(patched_files[0]), archive_path)

        if modified_file not in patched_files:
            return

        patch_files = {
            patch_file.path: calculate_hash(patch_file.path)
            for obj in file.objects.values()
            if (patch := imported_patches.get_patch(obj.assets_file.name, obj.path_id))
            for patch_file in patch.patches
        }

        root_key = PatchType.Patch.value

        if modified_file in hash_data.get(root_key, {}):
            patch_files = merge_patch_files(
                hash_data[root_key][modified_file]["patch_files"], patch_files
            )

        hash_data.setdefault(root_key, {})
        hash_data[root_key][modified_file] = {
            "hash": calculate_hash(modified_file),
            "patch_files": patch_files,
        }

    hashes = load_hashes()
    patched_files = game_loader.patched_files
    if not imported_patches or not patched_files:
        return

    for name, file in game_loader.env.files.items():
        if isinstance(file, (BundleFile, WebFile)):
            for inner_file in file.files.values():
                process_env_file(name, inner_file, hashes)
        else:
            process_env_file(name, file, hashes)

    save_hashes(hashes)
