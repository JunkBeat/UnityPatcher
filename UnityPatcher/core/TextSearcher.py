from dataclasses import dataclass
from typing import Optional, Tuple, Union, List
import logging
import os
import re

from enums import ExportType


@dataclass
class SearchResult:
    obj: object
    found_text: List[str]


def normalize(binary_data: bytes, case_sensitive: bool = True) -> bytes:
    """
    Normalize text by removing extra whitespace, tabs, and line breaks, 
    leaving only a single space. Optionally, converts the text to lowercase.
    """
    data = binary_data.decode("utf-8", errors="ignore")
    normalized_text = re.sub(r"\s+", " ", data).strip()

    if not case_sensitive:
        normalized_text = normalized_text.lower()

    return normalized_text.encode("utf-8")


def normalize_phrases(phrases: Union[str, List[str]], case_sensitive: bool = True) -> List[bytes]:
    if isinstance(phrases, str):
        phrases = [phrases]

    return [
        normalize(phrase.encode("utf-8"), case_sensitive)
        for phrase in phrases
    ]


def search_text_in_object(
    obj: object,
    search_phrases: List[bytes],
    case_sensitive: bool = False,
    whole_string: bool = False
) -> Optional[Tuple[object, List[str]]]:
    found_text = []
    raw_data = normalize(bytes(obj.get_raw_data()), case_sensitive)

    for phrase in search_phrases:
        if whole_string: 
            regex = rb'\b' + re.escape(phrase) + rb'\b' 
        else: 
            regex = re.escape(phrase)

        if re.search(regex, raw_data):
            found_text.append(phrase.decode("utf-8"))

    if found_text:
        return SearchResult(obj, found_text)

    return None


def export_objects(data: List[SearchResult], export_type: ExportType = ExportType.CONVERT):
    from core.ObjectHandler import ObjectHandler

    handler = ObjectHandler()
    mono_classes = set()

    for result in data:
        handler = handler.read(result.obj)
        handler.export_object(export_type)
        if handler.script_name:
            mono_classes.add(handler.script_name)

    handler.print_summary()
    if mono_classes:
        logging.info("\n[INF] Scripts: %s", ", ".join(sorted(mono_classes)))


def log_objects(data: List[SearchResult], path: str = "search_log.txt"):
    from core.ObjectHandler import ObjectHandler

    handler = ObjectHandler()
    mono_classes = set()

    dir_path = os.path.dirname(path) or "."
    if not os.access(dir_path, os.W_OK):
        raise PermissionError(f"No write access to file: {path}")

    with open(path, "w", encoding="utf-8") as log_file:
        for result in data:
            handler = handler.read(result.obj)
            info = handler.get_metadata_string()
            log_file.write(f"{info}\n\n[Found Texts]\n")
            log_file.writelines(f"- {text}\n" for text in result.found_text)
            log_file.write("\n" + "=" * 40 + "\n\n")
            if handler.script_name:
                mono_classes.add(handler.script_name)
        if mono_classes:
            log_file.write("Scripts: " + ", ".join(sorted(mono_classes)))

    logging.info("\n[INF] Successfully saved log: %s", path)
    