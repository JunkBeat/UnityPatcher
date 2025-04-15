import os
import io
import threading
from PIL import Image
from enums import TextureCompressionQuality as Quality

# BC1 - DXT1
# BC2 - DXT3
# BC3 - DXT5
# BC4 - RGTC1
# BC5 - RGTC2
# BC7 - BPTC

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


def compress_image_to_bc(
    img: Image, format_name: str, quality: Quality = Quality.BEST
) -> bytes:
    """
    Compress image to specified BC format using BCnEncoder.NET.

    :param img: Pil Image object
    :param format_name: BC format (BC1, BC2, BC3, BC4, BC5, BC7)
    :param quality: Compression quality (fast, balanced, best)
    :return: Compressed bytes
    """
    init_clr_once()

    from SixLabors.ImageSharp import Image as ImageSharpImage
    from SixLabors.ImageSharp.PixelFormats import Rgba32
    from BCnEncoder.ImageSharp import BCnEncoderExtensions
    from BCnEncoder.Encoder import BcEncoder, CompressionQuality
    from BCnEncoder.Shared import CompressionFormat, OutputFileFormat
    from System.IO import MemoryStream

    # Prepare input image
    img_bytearray = io.BytesIO() 
    pillow_img = img.convert("RGBA")
    pillow_img.save(img_bytearray, format="PNG") 

    ms = MemoryStream(img_bytearray.getvalue()) 
    try:
        input_memory = ImageSharpImage.Load[Rgba32](ms)
    finally:
        ms.Dispose()

    # Initialize encoder
    encoder = BcEncoder()
    format_map = {
        "BC1": CompressionFormat.Bc1,
        "BC2": CompressionFormat.Bc2,
        "BC3": CompressionFormat.Bc3,
        "BC4": CompressionFormat.Bc4,
        "BC5": CompressionFormat.Bc5,
        "BC7": CompressionFormat.Bc7,
    }
    quality_map = {
        "fast": CompressionQuality.Fast,
        "balanced": CompressionQuality.Balanced,
        "best": CompressionQuality.BestQuality,
    }
    if format_name not in format_map:
        raise ValueError(f"Unsupported format '{format_name}'.")
    encoder.OutputOptions.GenerateMipMaps = False
    encoder.OutputOptions.Format = format_map[format_name]
    encoder.OutputOptions.Quality = quality_map[quality.value]
    encoder.OutputOptions.FileFormat = OutputFileFormat.Dds

    # Compress the image
    output_stream = MemoryStream()
    try:
        BCnEncoderExtensions.EncodeToStream(encoder, input_memory, output_stream)
        compressed_bytes = output_stream.ToArray()
    finally:
        output_stream.Dispose()
    
    return bytes(compressed_bytes)[128:] # strip dds header
