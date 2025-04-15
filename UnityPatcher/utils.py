import logging
import os
import fnmatch
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from typing import Callable, List, Optional, Tuple, Union

import tkinter as tk
from tkinter import filedialog
from UnityPy.enums import ClassIDType

lock = threading.Lock()


def ask_directory(title="Select Directory"):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    directory = filedialog.askdirectory(title=title)
    root.destroy()  # Close the window after selecting the directory
    return directory


def run_multithread(worker: Callable, tasks: List[Tuple], max_workers: Optional[int] = None):
    cpu_count = os.cpu_count()
    max_workers = max_workers if (max_workers and max_workers <= cpu_count) else cpu_count

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(worker, tasks))


def create_pptr(object_reader, file_id: int, path_id: int):
    from io import BytesIO

    from UnityPy.classes import PPtr
    from UnityPy.streams import EndianBinaryReader, EndianBinaryWriter

    with BytesIO() as binary_data:
        writer = EndianBinaryWriter(binary_data, endian=object_reader.endian)

        writer.write_int(file_id)
        if object_reader.version2 < 14:
            writer.write_int(path_id)
        else:
            writer.write_long(path_id)

        binary_data.seek(0)

        new_reader = EndianBinaryReader(binary_data, endian=object_reader.endian)

        original_reader = object_reader.reader
        object_reader.reader = new_reader

        try:
            pptr = PPtr(reader=object_reader)
        finally:
            object_reader.reader = original_reader

    return pptr


def filter_objects(
    objects,
    asset_types: List[str] = None,
    asset_ids: List[int] = None,
    mono_classes: List[str] = None,
):
    asset_ids = asset_ids or []
    mono_classes = mono_classes or []
    asset_types = asset_types or []

    def is_valid_mono(obj):
        if obj.type == ClassIDType.MonoBehaviour and mono_classes:
            return get_mono_class_name(obj, log_exc=False) in mono_classes
        return True
    
    # filter by id
    if asset_ids and not mono_classes and not asset_types:
        return [obj for obj in objects if obj.path_id in asset_ids]

    # filter by type
    if asset_types and not asset_ids and not mono_classes:
        return [obj for obj in objects if obj.type.name in asset_types]

    # mixed filter
    filtered_objects = [
        obj
        for obj in objects
        if (not asset_ids or obj.path_id in asset_ids)
        and is_valid_mono(obj)
        and (
            obj.type.name in asset_types
            or (obj.type == ClassIDType.MonoBehaviour and mono_classes)
        )
    ]

    return filtered_objects


def get_mono_class_name(obj, log_exc=False) -> str:
    if obj.type == ClassIDType.MonoBehaviour:
        try:
            monobehaviour = obj.read(return_typetree_on_error=False)
            script_name = monobehaviour.m_Script.get_obj().read().name
            return script_name
        except Exception as e:
            if log_exc:
                traceback.print_exc()
                logging.warning(
                    "Can't read MonoBehaviour's script name: %s\n"
                    "Details: #%s, %s", 
                    e, obj.path_id, obj.assets_file.name
                )
                #print(bytes(obj.get_raw_data()))
            return None
    return None


def find_files_by_extensions(
    directory: str, extensions: List[str]
) -> List[str]:
    """
    Recursively finds all files in the specified folder with the specified extensions.

    :param directory: Path to the folder to search.
    :param extensions: List of file extensions to search.
    :return: List of files with the specified extensions.
    """
    matched_files = []
    for root, _, files in os.walk(directory):
        for ext in extensions:
            for filename in fnmatch.filter(files, f'*.{ext}'):
                matched_files.append(os.path.join(root, filename))
    return matched_files
