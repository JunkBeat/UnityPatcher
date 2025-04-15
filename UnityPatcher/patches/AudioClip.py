import os

from UnityPy import config
from UnityPy.classes import AudioClip
from UnityPy.enums import AudioCompressionFormat
from UnityPy.export import AudioClipConverter

from helpers import GeneralHelper, ResourcePacker
from tools import convert_to_fsb5
from utils import lock


def _AudioClip_set_audio(self: AudioClip, file: str, compress_to_fsb5: bool = True):
    if not file:
        raise ValueError("Audio file not provided")

    magic = GeneralHelper.read_binary_file(file, length=8)
    valid_formats = [b"OggS", b"RIFF", b"FSB5", b"ID3"]

    if not any(magic.startswith(fmt) for fmt in valid_formats):
        raise ValueError(f"Incorrect audio format: {file}. Expected ogg/wav/mp3/fsb5")

    if compress_to_fsb5:
        converter_formats = {"PCM", "XMA", "AT9", "Vorbis", "FADPCM", "OPUS", "MAX"}
        fmt_name = AudioCompressionFormat(self.m_CompressionFormat).name
        compression_format = fmt_name if fmt_name in converter_formats else "Vorbis"

        temp_path = config.TEMP_PATH
        os.makedirs(temp_path, exist_ok=True)
        output_file = os.path.join(temp_path, f"{self.name}.fsb")
        cache_folder = os.path.join(temp_path, "fsb5_cache")
        convert_to_fsb5(
            file,
            compression_format=compression_format,
            output_file_path=output_file,
            cache_folder_path=cache_folder,
            thread_count=os.cpu_count(),
        )
        self.m_AudioData = GeneralHelper.read_binary_file(output_file)

        if compression_format == "Vorbis":
            self.m_CompressionFormat = AudioCompressionFormat.Vorbis
    else:
        self.m_AudioData = GeneralHelper.read_binary_file(file)


def _AudioClip_save_via_tree(self: AudioClip, append_mode: bool = False):
    """
    append: True - write to the end of .resource
            False - replace the original audio/video
    """
    ResourcePacker(self, append_mode).pack()


def dump_samples(clip):
    with lock:
        pyfmodex = AudioClipConverter.pyfmodex

        if pyfmodex is None:
            AudioClipConverter.import_pyfmodex()
            pyfmodex = AudioClipConverter.pyfmodex

    if not pyfmodex:
        return {}

    # INVALID HANDLE fix
    with lock:
        system = pyfmodex.System()
        system.init(clip.m_Channels, pyfmodex.flags.INIT_FLAGS.NORMAL, None)

    try:
        sound = system.create_sound(
            bytes(clip.m_AudioData),
            pyfmodex.flags.MODE.OPENMEMORY,
            exinfo=pyfmodex.structure_declarations.CREATESOUNDEXINFO(
                length=clip.m_Size,
                numchannels=clip.m_Channels,
                defaultfrequency=clip.m_Frequency,
            ),
        )

        # iterate over subsounds
        samples = {}
        for i in range(sound.num_subsounds):
            if i > 0:
                filename = "%s-%i.wav" % (clip.name, i)
            else:
                filename = "%s.wav" % clip.name
            subsound = sound.get_subsound(i)
            samples[filename] = AudioClipConverter.subsound_to_wav(subsound)
            subsound.release()

        return samples

    finally:
        try:
            sound.release()
        except Exception:
            pass

        try:
            system.release()
        except Exception:
            pass


AudioClip.set_audio = _AudioClip_set_audio
AudioClip.save_via_tree = _AudioClip_save_via_tree
# thread-safe samples dumping
AudioClipConverter.dump_samples = dump_samples
