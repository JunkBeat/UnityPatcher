import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Добавляем текущую папку в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # Добавляем родительскую папку

import logging
import traceback
from tqdm import tqdm
import concurrent.futures
import UnityPy
from typing import List, Optional, Tuple, Union
from colorama import Fore, Style, init

from args import parse_args, print_help, process_asset_types
from core import GameLoader, ObjectHandler, PatchData, Statistics, TextSearcher
from core.Settings import Settings
from helpers import GeneralHelper, SmartPatching
from patches import *  # Import everything to apply patches on UnityPy
from utils import filter_objects, find_files_by_extensions, run_multithread
from enums import ExportType

# Initialize colorama
init(autoreset=True)

VERSION = "1.0.7.3"


class ColorFormatter(logging.Formatter):
    """Custom formatter for colored logging messages based on log level."""

    def format(self, record: logging.LogRecord) -> str:
        color_map = {
            logging.DEBUG: Fore.GREEN,
            logging.INFO: Fore.WHITE,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.MAGENTA,
        }
        record.msg = (
            f"{color_map.get(record.levelno, Fore.WHITE)}{record.msg}{Style.RESET_ALL}"
        )
        return super().format(record)


def configure_logging(debug=False):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter("%(message)s"))
    logger.addHandler(console_handler)
    return logger


def export_objects(
    objects: List[object],
    export_type: ExportType = ExportType.CONVERT,
    max_workers: Optional[int] = None,
) -> Statistics:
    stats = Statistics()
    tasks = [(export_type, obj, "SDF" in Settings.asset_types) for obj in objects]

    def worker(task: Tuple) -> None:
        ObjectHandler(stats).export_object(*task)

    run_multithread(worker, tasks, max_workers)
    stats.print_summary()

    return stats


def patch_objects(
    env: UnityPy.Environment,
    patch_data: PatchData,
    asset_types_filter: Optional[List[str]] = None,
    max_workers: int = 1,
) -> Statistics:
    sorted_patches = patch_data.sort_by_source()
    stats = Statistics()
    tasks = []

    def worker(task: Tuple) -> None:
        ObjectHandler(stats).patch_object(*task)

    for source_file, path_ids in sorted_patches.items():
        cab = env.get_cab(source_file)
        if not cab:
            continue

        for obj in cab.objects.values():
            if obj.path_id in path_ids:
                patch = get_patch_for_object(obj, patch_data)
                if patch and (
                    not asset_types_filter or obj.type.name in asset_types_filter
                ):
                    tasks.append((patch, obj))
                    patch.mark_detected()

    if tasks:
        if max_workers > 1:
            run_multithread(worker, tasks, max_workers)
        else:
            [worker(task) for task in tasks]

    stats.print_summary()
    if stats.success_count:
        print_unimported_assets(patch_data)

    return stats


def get_patch_for_object(obj, patch_data: PatchData) -> Tuple[PatchData]:
    try:
        handler = ObjectHandler()
        handler.read(obj)
    except Exception:
        logging.warning("[WARN] An exception occurred during getting the patch")
        logging.error(traceback.format_exc())
        return None, None

    patch = patch_data.get_patch(
        obj.assets_file.name,
        obj.path_id,
        script_name=handler.script_name,
        object_name=handler.name if not Settings.ignore_object_name else None,
    )
    return patch


def print_unimported_assets(patch_data: PatchData):
    undetected_assets = patch_data.undetected_assets

    if undetected_assets:
        logging.warning(
            "\n[WARN] %d assets from patch folder were not found. "
            "Possible reasons: filter by type, missing unity files, "
            "invalid id/source name specified in the name of patch files "
            "(see these assets in debug mode)",
            len(undetected_assets),
        )

    for asset in undetected_assets:
        logging.debug("%s - %s - #%d:", asset.name, asset.source_file, asset.path_id)
        for file in asset.patch_files:
            logging.debug("- %s", file.path)


def search_text_in_objects(
    objects: List[object],
    search_phrases: Union[str, List[str]],
    case_sensitive: bool = False,
    create_log: bool = False,
    export: bool = False,
    export_type: ExportType = ExportType.CONVERT,
    whole_string: bool = False
):
    data = []

    def worker(task: Tuple) -> None:
        result = TextSearcher.search_text_in_object(*task)
        if result:
            data.append(result)
    
    phrases = TextSearcher.normalize_phrases(search_phrases, case_sensitive)
    tasks = [(obj, phrases, case_sensitive, whole_string) for obj in objects]
    
    cpu_count = os.cpu_count()
    total_tasks = len(tasks)
    completed_tasks = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_count) as executor:
        futures = [executor.submit(worker, task) for task in tasks]
        for future in tqdm(concurrent.futures.as_completed(futures), total=total_tasks, desc="Task Progress"):
            completed_tasks += 1

    if not data:
        logging.warning("[WARN] Nothing found, check the command is correct")
        return

    logging.info("[INF] %d assets found", len(data))

    if export:
        TextSearcher.export_objects(data, export_type)

    if create_log:
        TextSearcher.log_objects(data)


class Patcher:
    def __init__(self, loader: GameLoader):
        self.loader = loader
        self.objects = loader.get_objects()
        self.game_folder = loader.game_folder

        Settings.game_folder = self.game_folder

    def unpack_assets(
        self,
        asset_types_filter: List[str] = None,
        asset_ids_filter: List[int] = None,
        mono_classes_filter: List[str] = None,
        output_folder: str = "Patcher_Assets",
        export_type: ExportType = ExportType.CONVERT,
        max_workers: int = None,
        unpack_all: bool = False,
    ):
        logging.info("\n[INF] Mode: Unpack")
        Settings.output_folder = output_folder

        if unpack_all:
            asset_types_filter.append("SDF")
            Settings.asset_types = asset_types_filter
        else:
            if "SDF" in asset_types_filter:
                mono_classes_filter.append("TMP_FontAsset")

            filters = {
                "Type": asset_types_filter,
                "Script": mono_classes_filter,
                "Id": map(str, asset_ids_filter) if asset_ids_filter else None,
            }

            if any(filters.values()):
                for name, filter_list in filters.items():
                    if filter_list:
                        logging.info(f"- Filter by {name}: %s", ", ".join(sorted(filter_list)))
                logging.info("")

        objects = self.objects

        if not unpack_all:
            objects = filter_objects(
                objects, asset_types_filter, asset_ids_filter, mono_classes_filter
            )
            if not objects:
                logging.warning("No assets were found for the specified query")
                return

        stats = export_objects(objects, export_type, max_workers)

        if stats.success_count > 0:
            logging.info("\nCheck output folder: %s", output_folder)

    def pack_assets(
        self,
        patch_folder: str = None,
        patch_data: PatchData = None,
        output_folder: str = "Patcher_Result",
        asset_types_filter: List[str] = None,
        packer: str = "original",
        max_workers: int = 1,
    ):
        self.loader.check_overwrite_permission(output_folder)

        logging.info("\n[INF] Mode: Pack")
        if asset_types_filter:
            logging.info("- Filter by Type: %s", ", ".join(sorted(asset_types_filter)))

        if patch_data is None:
            if not patch_folder or not os.path.isdir(patch_folder):
                raise ValueError("Patch folder is invalid or doesn't exist")
            patch_data = PatchData(patch_folder)

        if patch_data is None:
            logging.warning("No patch files found")
            return

        patch_objects(self.loader.env, patch_data, asset_types_filter, max_workers)
        self.loader.save_modified_files(output_folder, packer)

    def search_assets(
        self,
        search_text: str,
        create_log: bool = False,
        case_sensitive: bool = False,
        entire_search: bool = False,
        output_folder: str = "Patcher_Assets",
        export: bool = False,
        export_type: ExportType = ExportType.CONVERT,
        whole_string: bool = False
    ):
        Settings.output_folder = output_folder
        logging.info("\n[INF] Mode: Search")

        if os.path.exists(search_text):
            with open(search_text, encoding="utf-8") as file:
                search_text = [
                    line.encode("utf-8").decode("unicode_escape").strip()
                    for line in file
                ]
        else:
            search_text = [search_text]

        objects = (
            self.objects
            if entire_search
            else filter_objects(self.objects, ["TextAsset", "MonoBehaviour"])
        )

        search_text_in_objects(
            objects, search_text, case_sensitive, create_log, export, export_type, whole_string
        )


def setup_unitypy():
    UnityPy.config.TEMP_PATH = Settings.temp_path
    UnityPy.config.FALLBACK_UNITY_VERSION = Settings.fallback_version

    if Settings.cn_key:
        UnityPy.set_assetbundle_decrypt_key(Settings.cn_key)

    # use python typetree reader instead of C-extension
    # This will solve the dead freezing but it will work worse
    if Settings.python_typetree_reader:
        from UnityPy.helpers import TypeTreeHelper

        TypeTreeHelper.read_typetree_c = None


EXPORT_TYPE_MAPPINGS = {
    "normal": ExportType.CONVERT,
    "raw": ExportType.RAW,
    "dump": ExportType.DUMP,
}


def get_command_input():
    while True:
        print("\n-> Want to run another command to search or unpack?")
        print("-> You can disable this question with the --once option.")
        choice = input("\n-> Answer (y/n): ").strip().lower()

        if choice in ("n", "no", "q", "quit"):
            return None

        print('-> Example: search "some text" --export')
        command = input("-> Enter the command: ").strip()

        try:
            args = parse_args(command)
            if args.command in {"search", "unpack"}:
                return args

            logging.error("Invalid command. Please enter 'search' or 'unpack'.")
        except Exception as e:
            logging.error("An error occurred while processing arguments: %s", e)



def main(args):
    import subprocess
    subprocess.run(["title", f"UnityPatcher — v.{VERSION}"], shell=True)

    Settings.load_from_args(args)

    game_folder = args.game_folder or GeneralHelper.find_game_folder()
    Settings.game_folder = game_folder

    configure_logging(debug=Settings.debug_mode)
    logging.info("UnityPatcher by Artie Bow ʕ•ᴥ•ʔっ♡\n")

    setup_unitypy()
    asset_loader = GameLoader(game_folder)

    from helpers.TypeTreeManager import setup_managed

    managed = args.managed_path
    if managed:
        setup_managed(os.path.abspath(managed))

    if args.command == "unpack":
        asset_loader.load_game()
        patcher = Patcher(asset_loader)

        while True:
            output_folder = args.output_folder
            asset_types = process_asset_types(args)
            export_type = EXPORT_TYPE_MAPPINGS.get(args.export_mode, ExportType.CONVERT)
            patcher.unpack_assets(
                asset_types_filter=asset_types,
                asset_ids_filter=args.asset_ids,
                mono_classes_filter=args.mono_classes,
                output_folder=output_folder,
                export_type=export_type,
                max_workers=args.max_workers,
                unpack_all=args.unpack_all,
            )

            if args.once:
                break
            args = get_command_input()
            if args is None:
                break

    elif args.command == "search":
        asset_loader.load_game()
        patcher = Patcher(asset_loader)

        while True:
            export_type = EXPORT_TYPE_MAPPINGS.get(args.export_mode)
            patcher.search_assets(
                args.search_text,
                create_log=args.log_found_assets,
                case_sensitive=args.case_sensitive_search,
                
                entire_search=args.entire_search,
                output_folder=args.output_folder,
                export=bool(export_type),
                export_type=export_type,
            )

            if args.once:
                break
            args = get_command_input()
            if args is None:
                break

    elif args.command == "pack":
        smart_mode = args.smart_mode
        patch_folder = args.patch_folder
        output_folder = game_folder if args.outsamedir else args.output_folder

        patch_data = PatchData(patch_folder)

        if smart_mode:
            logging.warning("[WARN] Smart Mode is enabled")
            patch_data = SmartPatching.filter_patches(
                game_folder, output_folder, patch_data
            )

        if args.load_all_files:
            asset_loader.load_game()
        else:
            asset_loader.load_cabs(patch_data.source_names)

        patcher = Patcher(asset_loader)
        asset_types = process_asset_types(args)
        patcher.pack_assets(
            patch_data=patch_data,
            asset_types_filter=asset_types,
            packer=args.archive_packer,
            output_folder=output_folder,
            max_workers=args.max_workers or 1,
        )

        if smart_mode:
            logging.info("\n[INF] Updating hash data...")
            SmartPatching.update_hash_data(asset_loader, patch_data.imported_patches)


if __name__ == "__main__":
    cli_args = parse_args()
    if not vars(cli_args).get("command"):
        print_help()
        input("Press Enter...")
    else:
        main(cli_args)
