import argparse
import shlex
from enum import Enum
import os
from typing import List

from UnityPy.enums import ClassIDType

from enums import TextureCompressionQuality as TexQuality


class GroupingOptions(Enum):
    NONE = "none"
    TYPE = "type"
    SOURCE = "source"
    SOURCE_TYPE = "source_type"
    TYPE_SOURCE = "type_source"


class ExportModeOptions(Enum):
    NORMAL = "normal"
    RAW = "raw"
    DUMP = "dump"

    
def process_asset_types(args) -> List[str]:
    arg_to_types = {
        "audio": [ClassIDType.AudioClip.name],
        "texture": [ClassIDType.Texture2D.name, ClassIDType.Texture2DArray.name],
        "video": [ClassIDType.VideoClip.name],
        "text": [ClassIDType.TextAsset.name],
        "font": [ClassIDType.Font.name, "SDF"],
        "mb": [ClassIDType.MonoBehaviour.name],
    }

    asset_types = args.asset_types
    for arg, types in arg_to_types.items():
        if getattr(args, arg, False):
            asset_types.extend(types)

    return list(set(asset_types))


def create_parser():
    parser = argparse.ArgumentParser(
        description="UnityPatcher — a tool for working with Unity assets.",
        epilog=(
            "Examples of usage:\n"
            "  Patcher unpack --texture -c Text -i ./Game_Data/ -o ./ExtractedAssets/\n"
            "  Patcher pack ./Patches/ --outsamedir\n"
            "  Patcher search 'example text' --export"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    _add_unpack_arguments(subparsers)
    _add_pack_arguments(subparsers)
    _add_search_arguments(subparsers)
    
    return parser


def parse_args(command: str = None):
    parser = create_parser()
    if command:
        return parser.parse_args(shlex.split(command))
    return parser.parse_args()


def print_help():
    parser = create_parser()
    parser.print_help()


def _add_unpack_arguments(subparsers):
    unpack_parser = subparsers.add_parser("unpack", help="Extract Unity assets",)
    
    general_group = unpack_parser.add_argument_group("General Options")
    general_group.add_argument(
        "--threads",
        nargs="?",
        const=os.cpu_count(),
        type=int,
        dest="max_workers",
        help="Maximum number of threads to use. "
        "Default: number of CPU cores. Example: --threads 4."
    )
    general_group.add_argument(
        "-o",
        "--output_folder",
        default="Patcher_Assets",
        help="The folder where extracted assets will be saved. "
        "Default: \"Patcher_Assets\""
    )
    _add_shared_arguments(general_group)
    _add_asset_type_arguments(unpack_parser)

    unpack_parser.add_argument(
        "-g",
        "--group",
        choices=[opt.value for opt in GroupingOptions],
        default=GroupingOptions.TYPE.value,
        nargs="?",
        const="type",
        dest="group_option",
        help="Determine how exported assets will be grouped. Default: by type name",
    )
    unpack_parser.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=[opt.value for opt in ExportModeOptions],
        default=ExportModeOptions.NORMAL.value,
        dest="export_mode",
        help="Asset export mode. Default: normal mode",
    )
    unpack_parser.add_argument(
        "-c",
        "--classes",
        nargs="+",
        default=[],
        dest="mono_classes",
        help="Names of MonoBehaviour classes to extract (space-separated). "
        "Example: -c PlayerController EnemyAI."
    )
    unpack_parser.add_argument(
        "--id",
        nargs="+",
        type=int,
        default=[],
        dest="asset_ids",
        help="IDs of specific assets to extract (space-separated). "
        "Can be used with other filters. Example: --id 123 456."
    )
    unpack_parser.add_argument(
        "--all",
        action="store_true",
        dest="unpack_all",
        help="Extract all assets (not recommended)",
    )
    unpack_parser.add_argument(
        "--once",
        action="store_true",
        help="Terminate the program after completing the task",
    )


def _add_pack_arguments(subparsers):
    pack_parser = subparsers.add_parser("pack", help="Pack modified assets back into Unity files")

    general_group = pack_parser.add_argument_group("General Options")
    general_group.add_argument(
        "--threads",
        nargs="?",
        const=1,
        type=int,
        dest="max_workers",
        help="Maximum number of threads to use. "
        "Default: number of CPU cores. Example: --threads 4."
    )
    general_group.add_argument(
        "-o",
        "--output_folder",
        default="Patcher_Result",
        help="Path to the folder where packed files will be saved. "
        "Ignored if '--outsamedir' is specified. "
        "Example: -o ./PackedFiles/"
    )
    _add_shared_arguments(general_group)

    texture_group = pack_parser.add_argument_group("Texture Options")
    texture_group.add_argument(
        "--tex_quality",
        type=str,
        choices=[
            TexQuality.BALANCED.value,
            TexQuality.BEST.value,
            TexQuality.FAST.value,
        ],
        default=TexQuality.BEST,
        dest="texture_compression_quality",
        help="Texture compression quality. Default: best quality",
    )
    texture_group.add_argument(
        "--tex_mips",
        action="store_true",
        dest="generate_mipmaps",
        help="Generate mipmaps for textures",
    )
    texture_group.add_argument(
        "--raw_texture",
        action="store_true",
        dest="dont_compress_texture",
        help="Don't compress texture before packing",
    )

    video_group = pack_parser.add_argument_group("Video Options")
    video_group.add_argument(
        "--transcode",
        action="store_true",
        dest="transcode_video",
        help="Transcode video before packing",
    )
    video_group.add_argument(
        "--transcode_quality",
        type=str,
        choices=["low", "medium", "high"],
        default="medium",
        help="Video transcoding quality. Default: medium quality",
    )

    audio_group = pack_parser.add_argument_group("Audio Options")
    audio_group.add_argument(
        "--raw_audio",
        action="store_true",
        dest="dont_compress_audio",
        help="Don't compress audio in fsb before packing",
    )

    resource_group = pack_parser.add_argument_group("Resource Options")
    resource_group.add_argument(
        "--res_append",
        action="store_true",
        dest="resource_append_mode",
        help="Pack audio and video to the end of the resource file "
        "instead of replacing the original data",
    )
    resource_group.add_argument(
        "--custom_res",
        type=str,
        default="",
        help="Pack audio and video into a separate resource file "
        "(doesn't apply to bundles). "
        "Example: --custom_res \"my_res\""
    )

    _add_asset_type_arguments(pack_parser)

    pack_parser.add_argument(
        "patch_folder", 
        type=str, 
        help="Path to the folder containing modified asset files (patch files)."
    )
    pack_parser.add_argument(
        "--outsamedir",
        action="store_true",
        help="Output directory same as input "
        "(save packed files in the game folder, replacing original files)"
    )
    pack_parser.add_argument(
        "--packer",
        type=str,
        choices=["none", "original", "lz4", "lzma"],
        default="original",
        dest="archive_packer",
        help="Unity archive compression method. Default: as in the original",
    )
    pack_parser.add_argument(
        "--ignore_name",
        action="store_true",
        dest="ignore_object_name",
        help="When importing patch files, ignore the object names specified in the patch file names",
    )
    pack_parser.add_argument(
        "--smart",
        action="store_true",
        dest="smart_mode",
        help="Enable smart packing mode. Do not import files that have not been "
        "modified since the previous packaging.",
    )
    pack_parser.add_argument(
        "--load_all",
        action="store_true",
        dest="load_all_files",
        help="Load the entire game folder. May help avoid 'Can't load file: expected "
        "str, bytes or os.PathLike object' errors",
    )
    pack_parser.add_argument(
        "--recreate",
        action="store_true",
        dest="recreate_output_dir",
        help="Recreate the output folder instead of writing to it. Does not apply when "
        "packing directly into the game folder",
    )
    pack_parser.add_argument(
        "--backup",
        action="store_true",
        dest="backup_before_saving",
        help="Before saving modified files, make a backup (for each file, a backup is "
        "created only once in BACKUP directory)", 
    )


def _add_search_arguments(subparsers):
    search_parser = subparsers.add_parser("search", help="Search text within Unity assets")

    general_group = search_parser.add_argument_group("General Options")
    general_group.add_argument(
        "-o",
        "--output_folder",
        default="Patcher_Assets",
        help="Destination folder for exporting found assets",
    )
    _add_shared_arguments(general_group)

    search_parser.add_argument(
        "search_text",
        type=str,
        help="The string to search for or the path to a text file for line-by-line searching",
    )
    search_parser.add_argument(
        "--log",
        action="store_true",
        dest="log_found_assets",
        help="Write information about found assets to a log file",
    )
    search_parser.add_argument(
        "--case_sensitive",
        action="store_true",
        dest="case_sensitive_search",
        help="Enable case-sensitive search",
    )
    search_parser.add_argument(
        "--entire_search",
        action="store_true",
        help="Search in all objects, not just TextAsset and MonoBehaviour",
    )
    search_parser.add_argument(
        "--whole_string",
        action="store_true",
        help="Search for whole words only",
    )
    search_parser.add_argument(
        "--export",
        type=str,
        choices=[opt.value for opt in ExportModeOptions],
        nargs="?",
        const=ExportModeOptions.NORMAL.value,
        default="",
        dest="export_mode",
        help="Export assets where text was found",
    )
    search_parser.add_argument(
        "-g",
        "--group",
        choices=[opt.value for opt in GroupingOptions],
        default=GroupingOptions.TYPE.value,
        nargs="?",
        const="type",
        dest="group_option",
        help="Determine how exported assets will be grouped. Default: by type name",
    )
    search_parser.add_argument(
        "--once",
        action="store_true",
        help="Terminate the program after completing the task",
    )


def _add_shared_arguments(parser):
    """Adds shared arguments across commands."""
    parser.add_argument(
        "-i",
        "--input_folder",
        type=str,
        default="",
        dest="game_folder",
        help="Path to the folder containing game files. Example: -i ./Game_Data/",
    )
    parser.add_argument(
        "--blacklist",
        nargs="*",
        default=[],
        help="List of folders to blacklist (accepted full paths, relative paths, or folder names)",
    )
    parser.add_argument(
        "--managed",
        type=str,
        default="",
        dest="managed_path",
        help="Path to Managed folder",
    )
    parser.add_argument(
        "--fallback_version",
        default="2.5.0f5",
        help="Fallback Unity version to use if no version info is found. "
        "Example: --fallback_version 2021.3.7f1."
    )
    parser.add_argument(
        "--cn_key",
        default="",
        help="Decryption key for Unity CN's AssetBundle encryption",
    )
    parser.add_argument(
        "--py_typetree",
        action="store_true",
        dest="python_typetree_reader",
        help="Use Python's typetree reader instead of C-reader. This can help fix dead "
        "freez issues, but generally performs worse than the C-extension.",
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        dest="debug_mode", 
        help="Enable debug mode for more detailed logs."
    )


def _add_asset_type_arguments(parser):
    """Adds asset type-specific arguments to the parser."""
    asset_group = parser.add_argument_group("Asset Types")
    asset_group.add_argument(
        "-t",
        "--types",
        nargs="+",
        default=[],
        dest="asset_types",
        help="Specify asset types separated by a space for processing. "
        "Example: -t Texture2D Sprite TextAsset"
    )
    asset_group.add_argument(
        "--audio", action="store_true", help="Include audio assets"
    )
    asset_group.add_argument(
        "--texture", action="store_true", help="Include texture assets"
    )
    asset_group.add_argument(
        "--video", action="store_true", help="Include video assets"
    )
    asset_group.add_argument(
        "--text", action="store_true", help="Include text assets"
    )
    asset_group.add_argument(
        "--font", action="store_true", help="Include font assets"
    )
    asset_group.add_argument(
        "--mb", action="store_true", help="Include MonoBehaviour assets"
    )
