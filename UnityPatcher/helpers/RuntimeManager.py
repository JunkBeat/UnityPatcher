
from clr_loader import get_coreclr
from pythonnet import set_runtime
import threading
import logging
import os


class RuntimeManager:
    _runtime_initialized = False
    _lock = threading.Lock()

    @staticmethod
    def initialize_runtime(runtime_config_path=None):
        """
        Initializes the .NET Runtime with the specified configuration file.

        :param runtime_config_path: Path to runtimeconfig.json. If not specified, the default path is used.
        """
        with RuntimeManager._lock:
            if not RuntimeManager._runtime_initialized:
                try:
                    if runtime_config_path is None:
                        directory = os.path.dirname(os.path.abspath(__file__))
                        runtime_config_path = os.path.join(directory, "runtimeconfig.json")

                    if not os.path.exists(runtime_config_path):
                        raise FileNotFoundError(f"Runtime config not found: {runtime_config_path}")

                    set_runtime(get_coreclr(runtime_config=runtime_config_path))
                    RuntimeManager._runtime_initialized = True
                    logging.debug("Runtime successfully initialized with config: %s", runtime_config_path)

                except Exception as e:
                    logging.error("Failed to initialize runtime: %s", e)
                    raise
            else:
                logging.debug("Runtime is already initialized.")
                