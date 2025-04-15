import logging
import shutil
import os
import threading
from typing import List, Optional, Set, Generator

from UnityPy.environment import Environment
from UnityPy.files import BundleFile, WebFile
from UnityPy.streams import EndianBinaryReader

from core.Settings import Settings


def apply_bundle_patch():
    # backup read_files
    BundleFile._read_files = BundleFile.read_files

    def read_files_patch(self: BundleFile, blocksReader, m_DirectoryInfo):
        self.blocksReader = blocksReader
        self.directoryInfo = m_DirectoryInfo

    # overwrite the read_files to cache the values without directly parsing them
    BundleFile.read_files = read_files_patch

    # actually parse the given files with this function
    BundleFile.read_files_now = lambda self: self._read_files(
        self.blocksReader, self.directoryInfo
    )


def reset_bundle_patch():
    BundleFile.read_files = BundleFile._read_files


def recursive_assets_search(
    folder_path: str, 
    allowed_assets: Optional[List[str]] = None, 
    blacklist: Optional[List[str]] = None
):
    blacklist = set(blacklist or Settings.blacklist or [])
    ext_blacklist = {
        ".txt", ".png", ".wav", ".srt", ".xml", ".bmp", ".mp4", 
        ".dat", ".dll", ".jpg", ".json", ".manifest", ".rar", ".zip", ".7z",
        ".info", ".config"
    }
    allowed_base_names = {os.path.splitext(name)[0] for name in allowed_assets or []}

    for root, dirs, files in os.walk(folder_path):
        for dir_name in list(dirs):
            if (
                dir_name in blacklist or 
                os.path.abspath(dir_name) in blacklist or
                os.path.join(root, dir_name) in blacklist
            ):
                logging.info("Ignoring blacklisted folder: %s", os.path.join(root, dir_name))
                dirs.remove(dir_name)

        for file in files:
            base_name = file.split(".")[0]
            ext = os.path.splitext(file)[1]
            file_path = os.path.join(root, file)

            # load globalgamemanagers and data.unity3d
            if base_name.startswith("globalgamemanagers") or file == "data.unity3d":
                yield file_path
            # load necessary level files
            elif allowed_assets and file.startswith("level"):
                if file in allowed_assets:
                    yield file_path
                continue
            # load necessary assets file
            elif allowed_assets and ext in {".assets", ".resS", ".resource"}:
                if base_name in allowed_base_names:
                    yield file_path
                continue
            # load all other files whose extensions are not in the blacklist
            elif ext not in ext_blacklist:
                yield file_path


class CustomEnvironment(Environment):
    def __init__(self, *args, game_loader=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.game_loader = game_loader


class GameLoader:
    def __init__(self, game_folder: str):
        if not os.path.exists(game_folder):
            raise ValueError(f"Invalid game folder: {game_folder}")
        self.env = None
        self.game_folder = game_folder
        self.loaded_files = []
        self.patched_files = []
        self.loading_files = {}
        self.lock = threading.Lock()

    def try_load_file(self, file: str) -> bool:
        if file.startswith("archive:/"):
            file = file.split("/")[-1]

        if self.env.get_cab(file):
            return True

        with self.lock:
            if file in self.loading_files:
                event = self.loading_files[file]
                event.wait()
                return self.env.get_cab(file) is not None

            event = threading.Event()
            self.loading_files[file] = event

        try:
            full_path = os.path.join(self.game_folder, file)
            if os.path.isfile(full_path):
                logging.info("Loading %s...", full_path)
                self.load_file(full_path)
                return True
            if file.startswith("CAB"):
                apply_bundle_patch()
                success = self.parse_cabs([file])
                reset_bundle_patch()
                return success
            return False
        finally:
            with self.lock:
                event = self.loading_files.pop(file, None)
                if event:
                    event.set()

    def load_file(self, file_path: str):
        if not self.env:
            self.env = CustomEnvironment(game_loader=self)
        if file_path not in self.loaded_files:
            self.env.load_file(file_path)
            self.loaded_files.append(file_path)

    def load_assets(self, asset_names: List[str] = None) -> List[str]:
        paths = []
        self.env = CustomEnvironment(game_loader=self)
        paths.extend(list(recursive_assets_search(self.game_folder, asset_names)))
        self.env.load_assets(paths, lambda x: open(x, "rb"))
        self.loaded_files = paths
        return paths

    def load_game(self):
        logging.info("[INF] Loading: %s", self.game_folder)
        self.load_assets()

    def load_cabs(self, cab_names: List[str]):
        # Заменяем .sharedAssets на пустую строку для подгрузки всех
        # CAB, имя которых начинается с name
        asset_names = list(set(name.replace(".sharedAssets", "") for name in cab_names))
        logging.info("[INF] Loading: %s", self.game_folder)

        apply_bundle_patch()
        self.load_assets(asset_names)
        self.parse_cabs(asset_names)
        reset_bundle_patch()
        
        for asset in set(cab_names):
            if not self.env.get_cab(asset):
                logging.warning("[WARN] %s not found or is corrupted", asset)

    def get_objects(self):
        return self.env.objects

    def save_modified_files(self, output_folder: str, packer: str = "original"):
        if not any(getattr(file, "is_changed", False) for file in self.env.files.values()):
            return

        logging.info("\n[INF] Saving modified files...")
        self.patched_files = []

        if (
            Settings.recreate_output_dir
            and os.path.exists(output_folder)
            and output_folder != self.game_folder
        ):
            shutil.rmtree(output_folder)

        def save_env_file(file, saving_path: str):
            with open(saving_path, "wb") as f:
                if isinstance(file, EndianBinaryReader):
                    f.write(file.bytes)
                else:
                    f.write(file.save(packer=packer))

        def create_backup(original_path: str, archive_path: str):
            backup_path = os.path.join("BACKUP", archive_path)
            if not os.path.isfile(backup_path):
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy(original_path, backup_path)
                logging.info("[INF] Backup created")

        for file_path, file in self.env.files.items():
            if not getattr(file, "is_changed", False):
                continue

            archive_path = os.path.relpath(file_path, self.game_folder)
            dest_file = os.path.join(output_folder, archive_path)
            temp_file = dest_file + "_new"

            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            logging.info(" - %s", archive_path)

            if Settings.backup_before_saving:
                create_backup(file_path, archive_path)

            try:
                save_env_file(file, temp_file)
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.move(temp_file, dest_file)
                self.patched_files.append(dest_file)
            except Exception as e:
                logging.error("Error saving file %s: %s", dest_file, e)
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                continue

        if self.patched_files:
            logging.info("[INF] Saving completed! Check output folder: %s", output_folder)
        else:
            logging.warning("[WARN] No files were saved")

    def check_overwrite_permission(self, output_folder: str):
        locked_files = []

        for path in self.loaded_files:
            archive_path = os.path.relpath(path, self.game_folder)
            full_path = os.path.join(output_folder, archive_path)

            if os.path.exists(full_path):
                try:
                    with open(full_path, "a"):
                        pass
                except PermissionError:
                    locked_files.append(full_path)

        if locked_files:
            locked_files_list = "\n".join(locked_files)
            raise PermissionError(
                "Please close the programs in which the following files "
                f"are open:\n{locked_files_list}"
            )

    def parse_cabs(self, cab_names: List[str]) -> bool:
        parsed_at_least_one = False
        for filename, file in self.env.files.items():
            if not isinstance(file, (BundleFile, WebFile)):
                continue

            # read all cabs if file is data.unity3d and at least one asset matches
            should_read_bundle = (
                os.path.basename(filename) == "data.unity3d" 
                and any(
                    cab.path in cab_names
                    for cab in file.directoryInfo
                )
            )

            for cab in file.directoryInfo:
                cab_name = cab.path.split(".")[0]
                if should_read_bundle or cab_name in cab_names:
                    logging.info(
                        "[INF] Parsing %s...", os.path.basename(filename),
                    )
                    file.read_files_now()
                    parsed_at_least_one = True
                    break
        
        return parsed_at_least_one
