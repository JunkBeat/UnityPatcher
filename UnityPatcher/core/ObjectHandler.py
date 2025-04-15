import logging
import os
import traceback
from typing import List, Optional, Union

from UnityPy.classes.Object import NodeHelper
from UnityPy.enums import ClassIDType

import classes
from classes import SDF
from core.PatchFile import PatchData, PatchFile
from helpers import GeneralHelper
from enums import ExportType

class ExceptionData:
    def __init__(self, type_name: str, path_id: int, error_message: str, name: str = None):
        self.name = name
        self.type_name = type_name
        self.path_id = path_id
        self.error_message = error_message

class Statistics:
    def __init__(self):
        self.errors: List[ExceptionData] = []
        self.exceptions: List[ExceptionData] = []
        self.success_count: int = 0
        self.failure_count: int = 0

    def reset(self):
        self.errors = []
        self.exceptions = []
        self.success_count = 0
        self.failure_count = 0
        
    def increment_failure(self):
        self.failure_count += 1

    def increment_success(self):
        self.success_count += 1

    def log_error(self, handler: "ObjectHandler", error_msg: str, description: str = None, show_traceback: bool = True):
        self._log(handler, self.errors, error_msg, description, show_traceback)

    def log_exception(self, handler: "ObjectHandler", error_msg: str, description: str = None, show_traceback: bool = True):
        self._log(handler, self.exceptions, error_msg, description, show_traceback, count_failure=False)

    def _log(self, handler: "ObjectHandler", error_list: list, error_msg: str, error_description: str = None, show_traceback: bool = True, count_failure: bool = True):
        if count_failure:
            self.increment_failure()

        name = getattr(handler, "name", "Unknown Name")
        metadata = handler.get_metadata_string()

        logging.error(
            "%s\n\n[ERR] %s:\n%s",
            metadata,
            error_description or error_msg,
            traceback.format_exc() if show_traceback else "",
        )

        error_list.append(ExceptionData(handler.type_name, handler.path_id, error_msg, name=name))

    def print_summary(self) -> None:
        logging.info("%s", "-" * 50)

        def log_errors_or_exceptions(entries):
            for err in entries:
                logging.error(
                    "%s, %s #%d: %s",
                    err.name,
                    err.type_name,
                    err.path_id,
                    err.error_message,
                )
            logging.info("See the detailed report above.")
            logging.info("")

        if self.errors:
            logging.error("[ERR] Errors:")
            log_errors_or_exceptions(self.errors)

        if self.success_count == 0:
            logging.warning(
                "[WARN] No assets have been processed. Check your settings and paths."
            )
            return

        if self.exceptions:
            logging.warning("[WARN] Operation completed with the following exceptions:")
            log_errors_or_exceptions(self.exceptions)

        logging.info("Success: %d | Failures: %d", self.success_count, self.failure_count)


class ObjectHandler:
    def __init__(self, stats: Optional[Statistics] = None):
        self.obj = None
        self.type = None
        self.type_name = None
        self.path_id = None
        self.source_name = None
        self._manager = None
        self._name = None
        self.stats = stats or Statistics()

    def read(self, obj) -> "ObjectHandler":
        self.obj = obj
        self.type = obj.type
        self.type_name = obj.type.name
        self.path_id = obj.path_id
        self.source_name = obj.assets_file.name
        self.manager = self._get_object_manager()
        return self

    @property
    def manager(self) -> str:
        return self._manager

    @manager.setter
    def manager(self, inst):
        self._manager = inst
        self._name = inst.name

    @property
    def name(self) -> str:
        return self._name

    @property
    def script_name(self) -> Optional[str]:
        return self.manager.get_script_name() if self.manager else None

    def print_summary(self) -> None:
        self.stats.print_summary()

    def get_metadata_string(self) -> Optional[str]:
        return str(self.manager) if self.manager else None

    def try_read_object(self, obj) -> bool:
        try:
            if obj:
                self.read(obj)
            if self.obj is None:
                raise ValueError("Object not provided")
            return True
        except Exception as e:
            self.stats.log_exception(self, str(e))
            return False

    def read_dump(self) -> dict:
        return self.manager.read_typetree()

    def import_dump(self, dump: dict):
        self.manager.import_dump(dump)

    def export_object(self, export_type: ExportType = ExportType.CONVERT, obj: object = None, export_SDF = False):
        if not self.try_read_object(obj):
            return

        export_methods = {
            ExportType.CONVERT: self.export_normal,
            ExportType.RAW: self.export_raw,
            ExportType.DUMP: self.export_dump,
        }

        try:
            if export_SDF and self.script_name == "TMP_FontAsset":
                self.manager = SDF(self.manager.data)

            export_methods[export_type]()
            self.stats.increment_success()
        except Exception as e:
            self.stats.log_error(self, str(e))

    def export_normal(self):
        try:
            self.manager.export()
            self._log_success()
        except Exception as e:
            self.stats.log_exception(self, str(e), "Regular export failed")
            self.export_dump()

    def export_dump(self):
        self.manager.export_dump()
        self._log_success(as_dump=True)

    def export_raw(self):
        self.manager.export_raw()
        self._log_success(as_raw=True)

    def _log_success(self, as_dump=False, as_raw=False):
        suffix = " as dump" if as_dump else " as raw" if as_raw else ""
        script_info = f"@{self.script_name} " if self.script_name else ""
        logging.info(
            "[INF] Successfully saved %s%s: %s%s",
            self.type_name,
            suffix,
            script_info,
            self.name,
        )

    def patch_object(self, patch: Union[PatchData, PatchFile], obj: object = None):
        if not self.try_read_object(obj):
            return

        patches = [patch] if isinstance(patch, PatchFile) else patch.sort_by_file_type()
        regular_files: List[PatchFile] = []

        for file in patches:
            if file.is_raw:
                self._handle_import(lambda x: setattr(self.manager, "raw_data", x), file, "Raw import failed", raw=True)
            elif file.is_raw_content:
                self._handle_import(self.manager.import_raw_content, file, "Raw content import failed")
            elif file.is_dump:
                self._handle_import(self.manager.import_dump, file, "Dump import failed")
            else:
                regular_files.append(file)

        self._process_regular_files(regular_files)

    def _process_regular_files(self, files: List[PatchFile]):
        if not files:
            return

        if isinstance(self.manager, classes.DefaultManager):
            self.stats.log_error(self, "No suitable manager for the regular file", show_traceback=False)
            return

        if self.type == ClassIDType.Texture2DArray:
            self._handle_import(self.manager.import_, PatchData(files), "Regular file import failed")
        else:
            for file in files:
                self._handle_import(self.manager.import_, file, "Regular file import failed")

    def _handle_import(self, method, patch: Union[PatchData, PatchFile], error_description: str = None, raw=False):
        path_list = patch.paths if isinstance(patch, PatchData) else [patch.path]

        try:
            for path in path_list:
                data = GeneralHelper.read_binary_file(path) if raw else path
                method(data)

            self.stats.increment_success()
            patch.mark_imported()

            for path in path_list:
                logging.info("[INF] Successfully patched %s: %s", self.type_name, os.path.basename(path))
        except Exception as e:
            self.stats.log_error(self, str(e), error_description)

    def _get_object_manager(self):
        try:
            data = self.obj.read(return_typetree_on_error=False)
        except Exception as e:
            logging.warning("[WARN] Failed to parse object %d: %s", self.obj.path_id, e)
            return classes.DefaultManager(self.obj)

        if isinstance(data, NodeHelper):
            return classes.DefaultManager(self.obj)

        try:
            manager_class = getattr(classes, self.type_name, classes.DefaultManager)
            return manager_class(data)
        except Exception:
            logging.error("[ERR] Failed to create object manager for %s:\n%s", self.type_name, traceback.format_exc())
            raise
