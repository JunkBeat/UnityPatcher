import logging
from UnityPy.files import SerializedFile


def _SerializedFile_load_dependencies(self: SerializedFile, possible_dependencies: list = None):
    """Load all external dependencies.

    Parameters
    ----------
    possible_dependencies : list
        List of possible dependencies for cases
        where the target file is not listed as external.
    """
    for file_id in self.externals:
        try:
            self.environment.load_file(file_id.path, True)
        except Exception:
            logging.warning("Can't load dependency %s", file_id.path)
    if possible_dependencies:
        for dependency in possible_dependencies:
            try:
                self.environment.load_file(dependency, True)
            except Exception:
                logging.warning("Can't load possible dependency %s", dependency)


# Don't throw an exception if some dependency (which may not be needed) could not be loaded
SerializedFile.load_dependencies = _SerializedFile_load_dependencies
