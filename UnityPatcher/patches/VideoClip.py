import logging
import os
from enum import IntEnum

import ffmpeg  # ffmpeg-python
from UnityPy import config
from UnityPy.classes import VideoClip

from helpers import GeneralHelper, ResourcePacker


class VideoCompressionFormat(IntEnum):
    MP4 = 1
    WMV = 2
    VP9 = 3
    VP8 = 4


TRANSCODING_MAPPINGS = {
    VideoCompressionFormat.WMV: ("wmv2", "wmav2", ".asf"),
    VideoCompressionFormat.VP9: ("libvpx-vp9", "libvorbis", ".webm"),
    VideoCompressionFormat.VP8: ("libvpx", "libvorbis", ".webm"),
    VideoCompressionFormat.MP4: ("libx264", "aac", ".mp4"),
}

CODECS_MAPPINGS = {
    VideoCompressionFormat.WMV: ("wmv2", "wmav2"),
    VideoCompressionFormat.VP9: ("vp9", "vorbis"),
    VideoCompressionFormat.VP8: ("vp8", "vorbis"),
    VideoCompressionFormat.MP4: ("h264", "aac"),
}


def _VideoClip_set_video(
    self: VideoClip, file: str, transcode: bool = False, preset: str = "medium"
):
    if not os.path.isfile(file):
        raise FileNotFoundError(f"File not found: {file}")

    try:
        probe = ffmpeg.probe(file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"ffmpeg not found: {e}")

    video_stream = next(
        (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
        None,
    )

    if not video_stream:
        raise Exception(f"No video stream found: {file}")

    self.m_VideoData = (
        self.transcode_video(file, preset) if transcode else self.read_raw_video(file)
    )

    width = int(video_stream["width"])
    height = int(video_stream["height"])

    if width != self.Width or height != self.Height:
        logging.warning("New video's dimensions differ from the original")

    self.Width = width
    self.Height = height

    self.m_ProxyWidth = width
    self.m_ProxyHeight = height


def _VideoClip_check_codecs(self: VideoClip, file: str) -> bool:
    probe = ffmpeg.probe(file)
    codecs = {stream["codec_type"]: stream["codec_name"] for stream in probe["streams"]}
    expected_video_codec, expected_audio_codec = CODECS_MAPPINGS.get(self.m_Format)
    return (
        codecs.get("video") == expected_video_codec
        and codecs.get("audio") == expected_audio_codec
    )


def _VideoClip_check_validity(self: VideoClip, file: str) -> bool:
    probe = ffmpeg.probe(file)
    codecs = {stream["codec_type"]: stream["codec_name"] for stream in probe["streams"]}
    return codecs.get("video")


def _VideoClip_read_raw_video(self: VideoClip, file: str):
    if not self.check_validity(file):
        raise ValueError("The file does not contain a video stream.")
    return GeneralHelper.read_binary_file(file)


def _VideoClip_transcode_video(self: VideoClip, file: str, preset: str = "medium"):
    vcodec, acodec, ext = TRANSCODING_MAPPINGS.get(self.m_Format)

    if self.check_codecs(file):
        return GeneralHelper.read_binary_file(file)

    temp_path = config.TEMP_PATH
    os.makedirs(temp_path, exist_ok=True)
    output_file = os.path.join(temp_path, self.name + ext)
    logging.info("Converting video: %s...", file)
    (
        ffmpeg.input(file)
        .output(output_file, vcodec=vcodec, acodec=acodec, preset=preset)
        .run(quiet=True, overwrite_output=True)
    )
    return GeneralHelper.read_binary_file(output_file)


def _VideoClip_save_via_tree(self: VideoClip, append_mode: bool = False):
    ResourcePacker(self, append_mode).pack()
    self.m_VideoData = None # Freeing up memory


VideoClip.set_video = _VideoClip_set_video
VideoClip.transcode_video = _VideoClip_transcode_video
VideoClip.read_raw_video = _VideoClip_read_raw_video
VideoClip.check_codecs = _VideoClip_check_codecs
VideoClip.save_via_tree = _VideoClip_save_via_tree
VideoClip.check_validity = _VideoClip_check_validity
