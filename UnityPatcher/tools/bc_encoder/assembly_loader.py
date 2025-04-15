
import os
import sys

from helpers import RuntimeManager


def initialize_clr(lib_dir: str):
    """Load assembly references via CLR."""
    if not os.path.isdir(lib_dir):
        raise FileNotFoundError(f"Library directory not found: {lib_dir}")

    RuntimeManager.initialize_runtime()

    sys.path.append(lib_dir)

    # import clr after runtime is set and path is appended
    import clr

    for filename in os.listdir(lib_dir):
        split_file = os.path.splitext(filename)
        if split_file[1] == ".dll":
            clr.AddReference(os.path.join(lib_dir, filename))
