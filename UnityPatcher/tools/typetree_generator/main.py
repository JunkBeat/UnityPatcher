"""
Unity type tree generator

original author: jrobinson3k1
source: https://github.com/jrobinson3k1/typetree_unity
"""

import json
import logging
import os
import threading
from argparse import Namespace
from typing import List, Optional, Union

from .logger import get_logger, setup_logging

clr_initialized = False
clr_lock = threading.Lock()


def init_clr_once():
    global clr_initialized
    with clr_lock:
        if not clr_initialized:
            from .assembly_loader import initialize_clr

            lib_dir = os.path.join(os.path.dirname(__file__), "libs")
            initialize_clr(lib_dir)
            clr_initialized = True


def generate_typetree(
    assembly_folder: str,
    unity_version: str,
    class_names: Optional[Union[str, List[str]]] = None,
    enable_debug_output: bool = False,
    names_only: bool = False,
    output_file: str = None,
    libraries: Union[str, List[str]] = "Assembly-CSharp",
    disable_output: bool = False,
) -> dict:
    """
    Generate a typetree for the given classes.

    Args:
        assembly_folder (str): Path to the folder containing assembly files (DLLs).
        unity_version (str): Unity version to use for type tree generation.
        class_names (Union[str, List[str]]): List of class names or a single class
            name to generate type trees for. If not specified, all classes are dumped.
        enable_debug_output (bool, optional): Enables debug output. Default is False.
        names_only (bool, optional): If True, only outputs class names. Default is False.
        output_file (str, optional): Path to json file to write typetrees to. Default is None.
        libraries (Union[str, List[str]], optional): List of libraries or a single library
            to process. Default is "Assembly-CSharp".
        disable_output (bool, optional): If True, only displays critical messages. Default is False.

    Returns:
        dict: Dictionary containing the generated type trees for each specified class.
    """

    args = Namespace(
        assembly_folder=assembly_folder,
        unity_version=unity_version,
        class_names=[class_names] if isinstance(class_names, str) else class_names,
        enable_debug_output=enable_debug_output,
        names_only=names_only,
        output_file=output_file,
        libraries=[libraries] if isinstance(libraries, str) else libraries,
        disable_output=disable_output,
    )
    trees = main(args)
    return trees


def main(args) -> dict:
    level = logging.DEBUG if args.enable_debug_output else logging.INFO
    logger = setup_logging(level=level)

    if args.disable_output:
        logger.disabled = True

    init_clr_once()  # Initialize CLR only once

    from .generator import create_generator

    logger.debug("Creating generator with assembly_folder")
    generator = create_generator(
        args.assembly_folder, args.unity_version, args.libraries
    )

    if args.class_names:
        trees = generator.generate_type_trees(args.class_names)
    else:
        trees = generator.generate_type_trees()

    if trees:
        if args.names_only:
            trees = list(trees.keys())
            trees.sort()

        if args.output_file:
            export_type_tree(trees, args.output_file)

        return trees

    return None


def export_type_tree(tree, output_file):
    """
    Export type tree to JSON.

    Parameters
    ----------
    tree : dict[str, list]
        Type trees created from the generate_tree method
    output_file: str
        File path where type tree(s) will be exported
    """
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    if not os.access(output_dir, os.W_OK):
        raise RuntimeError("output file's directory is inaccessible")

    with open(output_file, "wt", encoding="utf8") as stream:
        json.dump(tree, stream, ensure_ascii=False)

    get_logger().info("Exported tree to %s", output_file)
