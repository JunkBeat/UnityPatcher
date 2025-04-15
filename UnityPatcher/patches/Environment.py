import io
import logging
import os
import re
from typing import Callable, List, Union

from UnityPy.environment import Environment
from UnityPy.files import File, SerializedFile
from UnityPy.enums import FileType
from UnityPy.helpers import ImportHelper
from UnityPy.streams import EndianBinaryReader


reSplit = re.compile(r"(.*?([^\/\\]+?))\.split\d+")


def _Environment_load_assets(
    self: Environment, assets: List[str], open_f: Callable[[str], io.IOBase]
):
    """
    Load all assets from a list of files via the given open_f function.

    Parameters
    ----------
    assets : List[str]
        List of files to load.
    open_f : Callable[[str], io.IOBase]
        Function to open the files.
        The function takes a file path and returns an io.IOBase object.
    """
    split_files = []
    for path in assets:
        splitMatch = reSplit.match(path)
        if splitMatch:
            basepath, basename = splitMatch.groups()

            if basepath in split_files:
                continue

            split_files.append(basepath)
            data = self._load_split_file(basepath)
            path = basepath
        else:
            data = open_f(path).read()

        # FIX
        try:
            self.load_file(data, name=path)
        except Exception:
            logging.debug("Invalid file skipped: %s", path)


def _Environment_load_file(
    self,
    file: Union[io.IOBase, str],
    parent: Union["Environment", File] = None,
    name: str = None,
    is_dependency: bool = False,
):
    def load_via_loader(file: str, e: str):
        if hasattr(self, "game_loader"):
            if not self.game_loader.try_load_file(file):
                raise Exception(f"Cant't load file {file}: {e}")
            return
        raise Exception(f"Cant't load file {file}: {e}")

    if not parent:
        parent = self

    if isinstance(file, str):
        split_match = reSplit.match(file)
        if split_match:
            basepath, basename = split_match.groups()
            name = basepath
            file = self._load_split_file(name)
        else:
            name = file
            if not os.path.exists(file):
                # relative paths are in the asset directory, not the cwd
                if not os.path.isabs(file):
                    # FIX: clear exception
                    try:
                        file = os.path.join(self.path, file)
                    except Exception as e:
                        load_via_loader(file, e)
                # for dependency loading of split files
                if os.path.exists(f"{file}.split0"):
                    file = self._load_split_file(file)
                # Unity paths are case insensitive, so we need to find "Resources/Foo.asset" when the record says "resources/foo.asset"
                elif not os.path.exists(file):
                    # FIX: clear exception
                    try:
                        file = ImportHelper.find_sensitive_path(self.path, file)
                    except Exception as e:
                        load_via_loader(file, e)
                # nonexistent files might be packaging errors or references to Unity's global Library/
                if file is None:
                    return
            if type(file) is str:
                file = self.fs.open(file, "rb")

    typ, reader = ImportHelper.check_file_type(file)

    stream_name = (
        name
        if name
        else getattr(
            file,
            "name",
            str(file.__hash__()) if hasattr(file, "__hash__") else "",
        )
    )

    if typ == FileType.ZIP:
        f = self.load_zip_file(file)
    else:
        f = ImportHelper.parse_file(
            reader, self, name=stream_name, typ=typ, is_dependency=is_dependency
        )
    
    if isinstance(f, (SerializedFile, EndianBinaryReader)):
        self.register_cab(stream_name, f)

    self.files[stream_name] = f


# "String not terimated" fix (skip invalid files)
Environment.load_assets = _Environment_load_assets

# Throw a clear exception when a file cannot be loaded + loading dependencies via game loader
Environment.load_file = _Environment_load_file
