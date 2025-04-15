import os
import subprocess

DIR = os.path.dirname(os.path.abspath(__file__))


def convert_to_fsb5(
    audio_path: str,
    compression_format: str = "Vorbis",
    output_file_name: str = None,
    output_folder_path: str = None,
    quality: int = 0,
    thread_count: int = 4,
    cache_folder_path: str = None,
    print_debug: bool = False,
    output_file_path: str = None,
):
    if not os.path.isfile(audio_path):
        raise FileNotFoundError("fsb5_converter", "File not found:", audio_path)

    command = [
        os.path.join(DIR, "fsb5_converter", "FSB5.Converter.exe"),
        "-a",
        audio_path,
        "-f",
        compression_format,
    ]

    if output_file_path:
        filepath, filename = os.path.split(output_file_path)
        command.extend(["-o", filepath])
        command.extend(["-n", filename.replace(".fsb", "")])
    else:
        if output_folder_path:
            command.extend(["-o", output_folder_path])
        if output_file_name:
            command.extend(["-n", output_file_name])

    if quality:
        command.append("-q")
        command.append(str(quality))
    if thread_count:
        command.append("-b")
        command.append(str(thread_count))
    if cache_folder_path:
        command.append("-c")
        command.append(cache_folder_path)
    if print_debug:
        command.append("-d")

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    out, err = process.communicate()
    retcode = process.poll()
    if retcode:
        raise Exception("fsb5_converter", err)
    return out, err
